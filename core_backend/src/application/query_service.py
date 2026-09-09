import time
import uuid
from typing import Any
from sqlalchemy.orm import Session
from .. import models
from ..database import sessionLocal
from ..milvus_store import milvus_store
from ..cache import query_cache
from ..grounding import verify_grounding

from ..retrieval.router import route_query
from ..retrieval.hybrid import reciprocal_rank_fusion
from ..retrieval.reranker import rerank_hits
from ..retrieval.confidence import evaluate_confidence
from ..generation.citations import build_citations
from ..generation.synthesizer import synthesize_answer

# Circular import workaround: we need _embed_query. It might be better to import from services or a utils module.
# Since services.py will be a shim, we can import _embed_query from services.
from ..services import _embed_query

async def answer_question(question: str, document_id: int | None = None, category: str | None = None, top_k: int = 5, bypass_llm: bool = False, organization_id: str = "org_default", group_ids: list[int] | None = None, as_of: str | None = None) -> dict[str, Any]:
    start_time = time.time()
    routed_categories = []
    query_vector = _embed_query(question)
    
    # Scope/Cache Check
    group_id = group_ids[0] if group_ids and len(group_ids) > 0 else None
    cached_payload = query_cache.get(
        org_id=organization_id,
        group_id=str(group_id) if group_id else "default_group",
        query=question,
        query_embedding=query_vector,
        as_of=as_of
    )
    if cached_payload:
        return cached_payload

    db: Session = sessionLocal()
    try:
        ready_count = db.query(models.Document).filter(models.Document.status == "ready").count()
        if ready_count == 0:
            processing_count = db.query(models.Document).filter(models.Document.status.in_(["uploaded", "processing"])).count()
            if processing_count > 0:
                return {"answer": "Your documents are currently being processed. Please wait a moment.", "citations": [], "gate_decision": "REFUSE"}
            return {"answer": "No documents are available in the system.", "citations": [], "gate_decision": "REFUSE"}
        
        hits = []

        if document_id is not None:
            doc = db.query(models.Document).filter(models.Document.id == document_id).first()
            if not doc or doc.status != "ready":
                return {"answer": "Document not ready or does not exist.", "citations": [], "gate_decision": "REFUSE"}
            
            search_k = max(15, top_k * 3)
            hits = milvus_store.search(query_text=question, query_embedding=query_vector, top_k=search_k, document_id=document_id, organization_id=organization_id, group_ids=group_ids)

        elif category is not None:
            doc_ids_query = db.query(models.Document.id).join(models.Document.categories).filter(
                models.Category.name == category, models.Document.status == "ready"
            ).all()
            doc_ids = [r[0] for r in doc_ids_query]
            if doc_ids:
                search_k = max(15, top_k * 3)
                hits = milvus_store.search(query_text=question, query_embedding=query_vector, top_k=search_k, document_ids=doc_ids, organization_id=organization_id, group_ids=group_ids)

        else:
            # Route
            top_cats = route_query(db, query_vector, top_k=3)
            if not top_cats:
                search_k = max(15, top_k * 3)
                hits = milvus_store.search(query_text=question, query_embedding=query_vector, top_k=search_k, organization_id=organization_id, group_ids=group_ids)
            else:
                routed_categories = top_cats
                doc_ids_query = db.query(models.Document.id).join(models.Document.categories).filter(
                    models.Category.name.in_(top_cats), models.Document.status == "ready"
                ).all()
                doc_ids = [r[0] for r in doc_ids_query]
                
                routed_hits = []
                if doc_ids:
                    routed_hits = milvus_store.search(query_text=question, query_embedding=query_vector, top_k=80, document_ids=doc_ids, organization_id=organization_id, group_ids=group_ids)
                
                global_hits = milvus_store.search(query_text=question, query_embedding=query_vector, top_k=40, organization_id=organization_id, group_ids=group_ids)
                
                hit_map = {}
                for hit in global_hits:
                    key = f"{hit['document_id']}_{hit['chunk_index']}"
                    hit_map[key] = hit
                
                for hit in routed_hits:
                    key = f"{hit['document_id']}_{hit['chunk_index']}"
                    hit["score"] = hit["score"] * 1.25 
                    if key not in hit_map or hit["score"] > hit_map[key]["score"]:
                        hit_map[key] = hit
                        
                hits = list(hit_map.values())
                hits.sort(key=lambda x: x["score"], reverse=True)
                hits = hits[:max(15, top_k * 3)]

    finally:
        db.close()

    # Security Assertions
    for chunk in hits:
        if chunk.get("organization_id") != organization_id:
            raise Exception(f"CRITICAL SECURITY EXCEPTION: Cross-tenant leakage detected! Chunk org {chunk.get('organization_id')} != Scope org {organization_id}. Trace ID: {uuid.uuid4()}")
        if group_ids is not None and chunk.get("group_id") not in group_ids:
            raise Exception(f"CRITICAL SECURITY EXCEPTION: Cross-group leakage detected! Chunk group {chunk.get('group_id')} not in Scope groups {group_ids}. Trace ID: {uuid.uuid4()}")

    if not hits:
        return {"answer": "The provided documents do not contain sufficient information.", "citations": [], "gate_decision": "REFUSE"}

    # Rerank
    hits = rerank_hits(question, hits, top_k)
    
    # Gate
    gate_decision = evaluate_confidence(hits)

    if gate_decision == "REFUSE":
        return {
            "answer": "I could not find sufficiently relevant information in the uploaded documents to answer this question.",
            "citations": [],
            "gate_decision": gate_decision
        }

    # Citations
    db = sessionLocal()
    try:
        citations = build_citations(db, hits)
    finally:
        db.close()

    # Synthesize
    answer = await synthesize_answer(question, hits, citations, gate_decision, bypass_llm)
        
    # NLI Grounding
    grounding_score = verify_grounding(answer, [hit["content"] for hit in hits])

    payload = {
        "answer": answer,
        "citations": citations,
        "gate_decision": gate_decision,
        "grounding_score": grounding_score
    }
    
    if gate_decision != "REFUSE":
        query_cache.set(
            org_id=organization_id,
            group_id=str(group_id) if group_id else "default_group",
            query=question,
            query_embedding=query_vector,
            response=payload,
            as_of=as_of
        )
        
    # Telemetry
    latency_ms = int((time.time() - start_time) * 1000)
    retrieved_chunk_ids = [c["chunk_id"] for c in citations]
    
    try:
        db_trace = sessionLocal()
        trace_record = models.QueryTrace(
            organization_id=organization_id,
            group_id=group_id,
            query_text=question,
            routed_categories=routed_categories,
            gate_decision=gate_decision,
            grounding_score=grounding_score,
            latency_ms=latency_ms,
            retrieved_chunk_ids=retrieved_chunk_ids
        )
        db_trace.add(trace_record)
        db_trace.commit()
    except Exception as e:
        print(f"Telemetry logging failed: {e}")
    finally:
        if 'db_trace' in locals():
            db_trace.close()

    return payload
