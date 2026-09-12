import asyncio
import os
from datetime import datetime
from typing import Any, Optional
from sqlalchemy import or_
from .config import EMBEDDING_MODEL, CROSS_ENCODER_MODEL, CROSS_ENCODER_THRESHOLD, LOG_RETRIEVAL_SCORES
from .cache import query_cache

from sqlalchemy.orm import Session

from . import models
from .database import sessionLocal
from .milvus_store import milvus_store

from sentence_transformers import SentenceTransformer, CrossEncoder

from .llm_service import generate_answer
from .config import (
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    DATABASE_URL,
)
from sqlalchemy import text

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader


def resolve_active_document_ids(db_session, group_id: int, as_of: Optional[datetime]) -> list[str]:
    """Resolve document IDs active at a given point in time.

    When as_of is None, returns only documents with is_current=True.
    When as_of is provided, executes a temporal point-in-time range query:
        valid_from <= as_of AND (valid_to IS NULL OR valid_to > as_of)
    """
    if as_of is None:
        versions = db_session.query(models.DocumentVersion).join(
            models.Document, models.Document.id == models.DocumentVersion.document_id
        ).filter(
            models.Document.group_id == group_id,
            models.DocumentVersion.is_current == True
        ).all()
    else:
        versions = db_session.query(models.DocumentVersion).join(
            models.Document, models.Document.id == models.DocumentVersion.document_id
        ).filter(
            models.Document.group_id == group_id,
            models.DocumentVersion.valid_from <= as_of,
            or_(
                models.DocumentVersion.valid_to == None,
                models.DocumentVersion.valid_to > as_of
            )
        ).all()
    return [str(v.document_id) for v in versions]


EMBEDDING_MODEL_INSTANCE = SentenceTransformer(
    EMBEDDING_MODEL
)





def _extract_text_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()

def _extract_summary_text_from_pdf(file_path: str) -> str:
    try:
        reader = PdfReader(file_path)
        total_pages = len(reader.pages)
        if total_pages == 0:
            return ""
        
        first_pages_limit = min(5, total_pages)
        first_pages_text = []
        for i in range(first_pages_limit):
            txt = reader.pages[i].extract_text()
            if txt:
                first_pages_text.append(txt)
                
        last_pages_text = []
        if total_pages > 5:
            last_pages_start = max(5, total_pages - 2)
            for i in range(last_pages_start, total_pages):
                txt = reader.pages[i].extract_text()
                if txt:
                    last_pages_text.append(txt)
                    
        parts = []
        if first_pages_text:
            parts.append("--- START OF DOCUMENT ---\n" + "\n".join(first_pages_text))
        if last_pages_text:
            parts.append("--- END OF DOCUMENT ---\n" + "\n".join(last_pages_text))
            
        return "\n\n".join(parts).strip()
    except Exception as e:
        print("Failed to extract summary text from PDF:", e)
        return ""

def _chunk_text(
    text: str,
) -> list[str]:

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=[
            "\n\n",
            "\n",
            ". ",
            " ",
            "",
        ],
    )

    return splitter.split_text(text)


def _embed_texts(texts: list[str]) -> list[list[float]]:
    vectors = EMBEDDING_MODEL_INSTANCE.encode(
        texts,
        normalize_embeddings=True
    )

    return [vector.tolist() for vector in vectors]


def _embed_query(text: str) -> list[float]:
    return _embed_texts([text])[0]


async def update_categorical_summary(category_name: str, group_ids: list[int] | None = None, bypass_llm: bool = False) -> None:
    """Consolidate document contents in the category and update its Milvus summary embedding."""
    if not category_name or category_name == "general":
        return

    db: Session = sessionLocal()
    try:
        # Fetch all documents in this category and group
        query = db.query(models.Document).join(models.Document.categories).filter(
            models.Category.name == category_name,
            models.Document.status == "ready"
        )
        if group_id is not None:
            query = query.filter(models.Document.group_id == group_id)
        docs = query.all()
        
        if not docs:
            return

        if bypass_llm:
            # Heuristic fallback summary for local offline, token-saving, or rate-limit testing
            doc_titles = ", ".join([d.filename for d in docs])
            summary_text = f"This category of documents covers topics related to {category_name}. It includes files like: {doc_titles}."
        else:
            # Compile summaries or first/last chunks of documents to create a category context
            context_parts = []
            for doc in docs:
                # Extract first 5 and last 2 pages of PDF on-the-fly
                doc_context = _extract_summary_text_from_pdf(doc.file_path)
                meta_info = f"Document: {doc.filename}\nSize: {doc.file_size or 0} bytes\n"
                context_parts.append(meta_info + doc_context[:4000])

            category_context = "\n\n".join(context_parts)
            
            # Call LLM to generate summary
            prompt = f"""
                Generate a concise, unified 2-3 sentence summary describing the scope and topic of this category of documents.
                Category Name: {category_name}
                Documents Context:
                {category_context}
            """
            
            try:
                from .llm_service import model
                response = await asyncio.to_thread(
                    model.generate_content,
                    prompt,
                )
                summary_text = response.text.strip()
            except Exception as exc:
                err_msg = str(exc)
                if "429" in err_msg or "quota" in err_msg.lower() or "limit" in err_msg.lower():
                    # Heuristic fallback summary for local offline or rate-limit testing
                    doc_titles = ", ".join([d.filename for d in docs])
                    summary_text = f"This category of documents covers topics related to {category_name}. It includes files like: {doc_titles}."
                else:
                    raise exc
        
        # Generate summary embedding
        summary_vector = _embed_query(summary_text)
        
        # Update summary in SQL
        cat_obj = db.query(models.Category).filter(
            models.Category.name == category_name,
            models.Category.group_id == group_id
        ).first()
        if cat_obj:
            cat_obj.summary = summary_text
            db.commit()

        # Upsert in Milvus
        milvus_store.upsert_category_summary(
            category_name=category_name,
            summary=summary_text,
            embedding=summary_vector,
            group_id=group_id
        )
        print(f"Updated category summary for '{category_name}' in group {group_id}: {summary_text[:100]}...")

    except Exception as exc:
        print("Failed to update categorical summary:", exc)
    finally:
        db.close()


async def consolidate_categories(group_id: int | None, bypass_llm: bool = False) -> None:
    """Consolidate/generalize specific categories under parent categories like 'Harry Potter Books', 'Novels', etc."""
    if bypass_llm:
        return
    db: Session = sessionLocal()
    try:
        # Get all distinct categories in the group
        categories = db.query(models.Category).filter(models.Category.group_id == group_id).all()
        if len(categories) < 2:
            return

        # Prepare summary list for LLM analysis
        candidates = []
        for cat in categories:
            candidates.append({
                "id": cat.id,
                "name": cat.name,
                "summary": cat.summary or ""
            })

        # Prompt Gemini to identify relationships and recommend consolidation/grouping
        prompt = f"""
            [SYSTEM: TAXONOMY ARCHITECT]
            You are an advanced ontology and taxonomy mapping agent. Your purpose is to analyze a flat list of active document categories in a user's workspace and design an elegant, hierarchical knowledge graph by identifying logical parent-child relationships.
            
            FLAT CATEGORIES LIST:
            {candidates}
            
            CONSOLIDATION PROTOCOL:
            1. HIERARCHY DETECTION: Identify sub-categories that naturally fall under broader, organizing "Parent Categories".
            2. PARENT NAMING: Synthesize clean, professional, and universally understood parent category names (e.g. "Science Fiction Novels", "HR Policies", "Machine Learning Publications", "Harry Potter Series").
            3. MULTIPLE INHERITANCE: A single sub-category CAN and SHOULD map to multiple parent categories if logically sound (e.g., "The Sorcerer's Stone" maps to both "Harry Potter Series" and "Fantasy Novels").
            4. ACTIONABLE OUTPUT ONLY: You must respond strictly with a valid JSON array of relationships. 
            
            JSON SCHEMA:
            [
                {{"parent_category": "Name of Broad Parent", "sub_category_ids": [id_1, id_2]}},
                {{"parent_category": "Another Parent", "sub_category_ids": [id_1, id_2, id_3]}}
            ]
            
            If the current categories are entirely disjoint and no grouping is logically possible, return an empty array: []
            
            Do NOT wrap your response in markdown code blocks. Output raw JSON only.
        """
        
        from .llm_service import model
        response = await asyncio.to_thread(
            model.generate_content,
            prompt,
        )
        import json
        import re
        raw_text = response.text.strip()
        # Find JSON array boundaries to prevent errors if the LLM includes preamble or postamble
        match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        if match:
            raw_text = match.group(0)
        else:
            raw_text = "[]"
            
        if not raw_text or raw_text == "[]":
            return
            
        consolidations = json.loads(raw_text)
        for entry in consolidations:
            parent_name = entry.get("parent_category")
            sub_ids = entry.get("sub_category_ids", [])
            if not parent_name or not sub_ids:
                continue
                
            # Create or get parent category
            parent_cat = db.query(models.Category).filter(
                models.Category.name == parent_name,
                models.Category.group_id == group_id
            ).first()
            if not parent_cat:
                parent_cat = models.Category(name=parent_name, group_id=group_id)
                db.add(parent_cat)
                db.commit()
                db.refresh(parent_cat)

            # Associate all documents from sub-categories to this parent category
            sub_categories = db.query(models.Category).filter(models.Category.id.in_(sub_ids)).all()
            for sub_cat in sub_categories:
                for doc in sub_cat.documents:
                    if parent_cat not in doc.categories:
                        doc.categories.append(parent_cat)
            
            db.commit()
            
            # Rewrite parent category summary
            await update_categorical_summary(parent_name, group_id, bypass_llm=bypass_llm)

    except Exception as e:
        print("Failed to consolidate categories:", e)
    finally:
        db.close()


async def process_document_task(doc_id: int, filename: str, bypass_llm: bool = False) -> None:
    """Background ingestion pipeline for uploaded PDFs."""
    db: Session = sessionLocal()
    try:
        doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
        if not doc:
            return

        doc.status = "processing"
        db.commit()

        from .chunking_engine import extract_blocks_from_pdf, chunk_structural_blocks
        from .enrichment_engine import enrich_chunks_with_context
        
        blocks = extract_blocks_from_pdf(doc.file_path)
        if not blocks:
            doc.status = "failed"
            db.commit()
            return

        structured_chunks = chunk_structural_blocks(blocks, bypass_llm=bypass_llm)
        if not structured_chunks:
            doc.status = "failed"
            db.commit()
            return
            
        # Apply contextual enrichment (gated behind bypass_llm)
        # Note: We need full_document_text for the LLM. In a real scenario, we could extract it from blocks.
        full_text_approx = "\n".join([b["text"] for b in blocks if "text" in b])
        structured_chunks = enrich_chunks_with_context(full_text_approx, structured_chunks, bypass_llm=bypass_llm)

        # --- Dynamic Automated Categorization ---
        is_general_only = len(doc.categories) == 1 and doc.categories[0].name == "general"
        if not doc.categories or is_general_only:
            summary_context_text = _extract_summary_text_from_pdf(doc.file_path)
            meta_info = f"Filename: {doc.filename}\nFile Size: {doc.file_size or 0} bytes\n"
            context_for_classification = meta_info + summary_context_text
            
            resolved_category_name = "general"
            # 1. Try vector-based matching against existing summaries
            first_chunk_text = structured_chunks[0]["text"] if structured_chunks else ""
            first_chunk_vector = _embed_query(summary_context_text[:1000] if summary_context_text else first_chunk_text)
            try:
                matches = milvus_store.search_categories(first_chunk_vector, top_k=1, group_id=doc.group_id)
                if matches and matches[0]["score"] >= 0.60:
                    resolved_category_name = matches[0]["category_name"]
                    print(f"Vector-matched category: {resolved_category_name} (score: {matches[0]['score']})")
            except Exception as e:
                print("Milvus category search skipped/failed:", e)
 
            # 2. Fallback to LLM Classification
            if resolved_category_name == "general" and not bypass_llm:
                try:
                    # Get unique category names in this group from PostgreSQL
                    categories_objs = db.query(models.Category).filter(models.Category.group_id == doc.group_id).all()
                    existing_categories = [c.name for c in categories_objs if c.name != "general"]
                    
                    from . import llm_service
                    resolved_category_name = await llm_service.classify_ingested_document(
                        text_sample=context_for_classification[:4000],
                        existing_categories=existing_categories
                    )
                    print(f"LLM-classified category: {resolved_category_name}")
                except Exception as e:
                    print("LLM classification failed, fallback to general:", e)
                    resolved_category_name = "general"
 
            # Create or get category in Postgres
            db_category = db.query(models.Category).filter(
                models.Category.name == resolved_category_name,
                models.Category.group_id == doc.group_id
            ).first()
            if not db_category:
                db_category = models.Category(name=resolved_category_name, group_id=doc.group_id)
                db.add(db_category)
                db.commit()
                db.refresh(db_category)
                
            # If we resolved a category different from "general", clear the "general" placeholder
            if is_general_only and resolved_category_name != "general":
                general_cat = db.query(models.Category).filter(
                    models.Category.name == "general",
                    models.Category.group_id == doc.group_id
                ).first()
                if general_cat in doc.categories:
                    doc.categories.remove(general_cat)
            
            if db_category not in doc.categories:
                doc.categories.append(db_category)
            db.commit()

        # Parent-Child Insertion Logic
        # We embed and insert ONLY the children into Milvus.
        # We store both Parents and Children in PostgreSQL.
        db.query(models.DocumentChunk).filter(models.DocumentChunk.document_id == doc_id).delete()
        
        child_texts_to_embed = []
        child_refs = [] # Keep track of which parent this child belongs to
        
        for parent_idx, p_chunk in enumerate(structured_chunks):
            # Save Parent to DB
            parent_db = models.DocumentChunk(
                document_id=doc_id,
                chunk_index=parent_idx * 1000, # space out indices
                content=p_chunk["text"],
                context_prefix=p_chunk.get("context_prefix", ""),
                page_from=p_chunk["page_from"],
                section_path=p_chunk["section_path"]
            )
            db.add(parent_db)
            db.flush() # get parent_db.id
            
            for child_idx, child_text in enumerate(p_chunk["children"]):
                c_prefix = p_chunk.get("child_contexts", [""] * len(p_chunk["children"]))[child_idx]
                # We embed the prefix + the content
                child_texts_to_embed.append(c_prefix + "\n" + child_text if c_prefix else child_text)
                _cspan = p_chunk.get("child_spans", [])
                _cs = _cspan[child_idx] if child_idx < len(_cspan) else {"char_start": 0, "char_end": 0}
                child_refs.append({
                    "parent_id": parent_db.id,
                    "chunk_index": parent_idx * 1000 + child_idx + 1,
                    "page_from": p_chunk["page_from"],
                    "section_path": p_chunk["section_path"],
                    "text": child_text,
                    "context_prefix": c_prefix,
                    "char_start": _cs["char_start"],
                    "char_end": _cs["char_end"],
                })

        embeddings = _embed_texts(child_texts_to_embed)
        
        # Insert children into Milvus
        _child_char_spans = [{"char_start": r["char_start"], "char_end": r["char_end"]} for r in child_refs]
        milvus_ids = milvus_store.upsert_chunks(
            document_id=doc_id,
            chunks=child_texts_to_embed,
            embeddings=embeddings,
            organization_id=doc.organization_id if doc.organization_id else "org_default",
            char_spans=_child_char_spans,
        )
        
        # Save children to DB with Milvus IDs and parent_chunk_id
        for i, ref in enumerate(child_refs):
            child_db = models.DocumentChunk(
                document_id=doc_id,
                chunk_index=ref["chunk_index"],
                content=ref["text"],
                context_prefix=ref["context_prefix"],
                milvus_id=str(milvus_ids[i]) if i < len(milvus_ids) else None,
                parent_chunk_id=ref["parent_id"],
                page_from=ref["page_from"],
                section_path=ref["section_path"],
                char_start=ref.get("char_start", 0),
                char_end=ref.get("char_end", 0),
            )
            db.add(child_db)

        doc.status = "ready"
        db.commit()
        print(
            f"DOCUMENT {doc_id} FINISHED"
        )   

        # Trigger summary update for all categories associated with this document
        for cat in doc.categories:
            await update_categorical_summary(cat.name, doc.group_id, bypass_llm=bypass_llm)

        # Trigger dynamic parent category consolidation / merging
        await consolidate_categories(doc.group_id, bypass_llm=bypass_llm)

    except Exception as exc:  # pragma: no cover - safety path for async task
        db.rollback()
        doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
        if doc:
            doc.status = "failed"
            db.commit()
    finally:
        db.close()



import math
import time
import uuid


from .application.query_service import answer_question
async def delete_document_assets(document_id: int, file_path: str | None) -> None:
    """Delete physical file + Milvus vectors for a document."""
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
    milvus_store.delete_document_chunks(document_id)

async def reset_system() -> None:

    print("RESET STARTED")

    db: Session = sessionLocal()

    try:

        print("STEP 1")

        uploads_dir = "uploads"

        if os.path.exists(uploads_dir):
            for file_name in os.listdir(uploads_dir):
                file_path = os.path.join(
                    uploads_dir,
                    file_name,
                )

                if os.path.isfile(file_path):
                    os.remove(file_path)

        print("STEP 2")

        milvus_store.delete_all_chunks()
        db.query(models.DocumentCategory).delete()
        db.query(models.DocumentChunk).delete()
        db.query(models.Document).delete()
        db.query(models.Category).delete()
        db.commit()

        print("AFTER TRUNCATE")

        if "postgresql" in DATABASE_URL:
            db.execute(text("ALTER SEQUENCE documents_id_seq RESTART WITH 1"))
            db.execute(text("ALTER SEQUENCE document_chunks_id_seq RESTART WITH 1"))
            db.execute(text("ALTER SEQUENCE categories_id_seq RESTART WITH 1"))
            db.commit()
            
            result = db.execute(text("SELECT nextval('documents_id_seq')"))
            print("NEXTVAL AFTER RESET =", result.scalar())
        else:
            print("SQLite - Sequences auto-reset on empty tables.")
    finally:

        print("STEP 7")

        db.close()










