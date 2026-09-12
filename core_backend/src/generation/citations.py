from sqlalchemy.orm import Session
from .. import models

def build_citations(db_session: Session, hits: list[dict]) -> list[dict]:
    citations = []
    for hit in hits:
        chunk_db = db_session.query(models.DocumentChunk).filter(
            models.DocumentChunk.document_id == hit["document_id"],
            models.DocumentChunk.chunk_index == hit["chunk_index"]
        ).first()
        
        page_from = chunk_db.page_from if chunk_db else None
        section_path = chunk_db.section_path if chunk_db else None
        char_start = chunk_db.char_start if chunk_db else hit.get("char_start", 0)
        char_end   = chunk_db.char_end   if chunk_db else hit.get("char_end",   0)
        
        if chunk_db and chunk_db.parent_chunk_id:
            parent_db = db_session.query(models.DocumentChunk).filter(
                models.DocumentChunk.id == chunk_db.parent_chunk_id
            ).first()
            if parent_db:
                hit["content"] = parent_db.content
        
        citations.append({
            "document_id": hit["document_id"],
            "chunk_id": f"{hit['document_id']}_{hit['chunk_index']}",
            "page_from": page_from,
            "section_path": section_path,
            "char_start": char_start,
            "char_end": char_end,
            "score": hit.get("cross_score", hit.get("score", 0.0)),
            "prob_relevant": hit.get("prob_relevant", 0.0),
            "content_preview": hit["content"][:220]
        })
    return citations
