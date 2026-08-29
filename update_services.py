import re

with open("core_backend/src/services.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove bm25_store import
content = re.sub(r'from \.bm25_store import bm25_store\n', '', content)

# 2. Update milvus_hits = milvus_store.search(...) everywhere in answer_question
# Since we have multiple search calls, let's just replace the answer_question function entirely.

def get_new_answer_question():
    return '''
import math

def sigmoid(x):
    return 1 / (1 + math.exp(-x))

async def answer_question(question: str, document_id: int | None = None, category: str | None = None, top_k: int = 5, bypass_llm: bool = False) -> dict[str, Any]:
    """Retrieve relevant chunks from Milvus and build a grounded response payload."""
    db: Session = sessionLocal()
    try:
        ready_count = db.query(models.Document).filter(models.Document.status == "ready").count()
        if ready_count == 0:
            processing_count = db.query(models.Document).filter(models.Document.status.in_(["uploaded", "processing"])).count()
            if processing_count > 0:
                return {"answer": "Your documents are currently being processed. Please wait a moment.", "citations": [], "gate_decision": "REFUSE"}
            return {"answer": "No documents are available in the system.", "citations": [], "gate_decision": "REFUSE"}
        
        query_vector = _embed_query(question)
        hits = []

        # 1. Specific Document ID Filter
        if document_id is not None:
            doc = db.query(models.Document).filter(models.Document.id == document_id).first()
            if not doc or doc.status != "ready":
                return {"answer": "Document not ready or does not exist.", "citations": [], "gate_decision": "REFUSE"}
            
            search_k = max(15, top_k * 3)
            hits = milvus_store.search(query_text=question, query_embedding=query_vector, top_k=search_k, document_id=document_id)

        # 2. Specific Category Filter
        elif category is not None:
            doc_ids_query = db.query(models.Document.id).join(models.Document.categories).filter(
                models.Category.name == category, models.Document.status == "ready"
            ).all()
            doc_ids = [r[0] for r in doc_ids_query]
            if doc_ids:
                search_k = max(15, top_k * 3)
                hits = milvus_store.search(query_text=question, query_embedding=query_vector, top_k=search_k, document_ids=doc_ids)

        # 3. Soft Multi-Category Routing (Issue 7)
        else:
            try:
                matches = milvus_store.search_categories(query_vector, top_k=3)
            except Exception as exc:
                print("Milvus search_categories failed:", exc)
                matches = []

            if not matches or matches[0]["score"] < 0.4:
                print("Router confidence low, skipping category filter. Global search initiated.")
                search_k = max(15, top_k * 3)
                hits = milvus_store.search(query_text=question, query_embedding=query_vector, top_k=search_k)
            else:
                top_cats = [m["category_name"] for m in matches]
                print(f"Soft Routing to Top-3 categories: {top_cats}")
                
                doc_ids_query = db.query(models.Document.id).join(models.Document.categories).filter(
                    models.Category.name.in_(top_cats), models.Document.status == "ready"
                ).all()
                doc_ids = [r[0] for r in doc_ids_query]
                
                routed_hits = []
                if doc_ids:
                    routed_hits = milvus_store.search(query_text=question, query_embedding=query_vector, top_k=80, document_ids=doc_ids)
                
                global_hits = milvus_store.search(query_text=question, query_embedding=query_vector, top_k=40)
                
                # Merge and apply 1.25x boost to routed hits
                hit_map = {}
                for hit in global_hits:
                    key = f"{hit['document_id']}_{hit['chunk_index']}"
                    hit_map[key] = hit
                
                for hit in routed_hits:
                    key = f"{hit['document_id']}_{hit['chunk_index']}"
                    hit["score"] = hit["score"] * 1.25 # Apply 1.25x boost
                    if key not in hit_map or hit["score"] > hit_map[key]["score"]:
                        hit_map[key] = hit
                        
                hits = list(hit_map.values())
                hits.sort(key=lambda x: x["score"], reverse=True)
                hits = hits[:max(15, top_k * 3)]

    finally:
        db.close()

    if not hits:
        return {"answer": "The provided documents do not contain sufficient information.", "citations": [], "gate_decision": "REFUSE"}

    # =========================================================================
    # STAGE 2: CROSS-ENCODER RERANKING & CONFIDENCE GATE (Issue 8)
    # =========================================================================
    print(f"\\n[RERANKING] Scoring {len(hits)} hits...")
    cross_input = [[question, hit["content"]] for hit in hits]
    scores = CROSS_ENCODER_INSTANCE.predict(cross_input)
    
    for idx, hit in enumerate(hits):
        hit["cross_score"] = float(scores[idx])
        # Platt scaling approximation (sigmoid)
        hit["prob_relevant"] = sigmoid(hit["cross_score"])
        
    hits.sort(key=lambda x: x["prob_relevant"], reverse=True)
    hits = hits[:top_k]

    top_prob = hits[0]["prob_relevant"] if hits else 0.0
    gate_decision = "ANSWER"
    
    # 3-Tier Gate
    if top_prob < 0.35:
        gate_decision = "REFUSE"
    elif top_prob < 0.70:
        gate_decision = "HEDGED"

    if gate_decision == "REFUSE":
        return {
            "answer": "I could not find sufficiently relevant information in the uploaded documents to answer this question.",
            "citations": [],
            "gate_decision": gate_decision
        }

    # =========================================================================
    # STAGE 3: STRUCTURED CITATIONS (Issue 9)
    # =========================================================================
    db = sessionLocal()
    citations = []
    try:
        for hit in hits:
            # Lookup page and section from PostgreSQL
            chunk_db = db.query(models.DocumentChunk).filter(
                models.DocumentChunk.document_id == hit["document_id"],
                models.DocumentChunk.chunk_index == hit["chunk_index"]
            ).first()
            
            page_from = chunk_db.page_from if chunk_db else None
            section_path = chunk_db.section_path if chunk_db else None
            
            # Use parent chunk context if available
            if chunk_db and chunk_db.parent_chunk_id:
                parent_db = db.query(models.DocumentChunk).filter(
                    models.DocumentChunk.id == chunk_db.parent_chunk_id
                ).first()
                if parent_db:
                    hit["content"] = parent_db.content
            
            citations.append({
                "document_id": hit["document_id"],
                "chunk_id": f"{hit['document_id']}_{hit['chunk_index']}",
                "page_from": page_from,
                "section_path": section_path,
                "score": hit["cross_score"],
                "prob_relevant": hit["prob_relevant"],
                "content_preview": hit["content"][:220]
            })
    finally:
        db.close()

    context_lines = [
        f"[Source {idx + 1}] (Page {cit.get('page_from', 'N/A')}, {cit.get('section_path', 'N/A')}): {hit['content']}" 
        for idx, (cit, hit) in enumerate(zip(citations, hits))
    ]
    context = "\\n\\n".join(context_lines)

    answer = await generate_answer(
        question=question,
        context=context,
        bypass_llm=bypass_llm,
    )
    
    if gate_decision == "HEDGED":
        answer = "Based on limited available documentation, " + answer

    return {
        "answer": answer,
        "citations": citations,
        "gate_decision": gate_decision
    }
'''

# Find everything from async def answer_question to the end of the file
pattern = r'async def answer_question\(question: str.*?return \{\s*"answer": answer,\s*"citations": citations,\s*\}\s*'
content = re.sub(pattern, get_new_answer_question(), content, flags=re.DOTALL)

with open("core_backend/src/services.py", "w", encoding="utf-8") as f:
    f.write(content)

print("services.py updated successfully.")
