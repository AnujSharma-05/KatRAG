from sentence_transformers import CrossEncoder
from ..config import CROSS_ENCODER_MODEL

CROSS_ENCODER_INSTANCE = CrossEncoder(CROSS_ENCODER_MODEL, max_length=256)

def rerank_hits(question: str, hits: list[dict], top_k: int) -> list[dict]:
    if not hits:
        return []
    print(f"\n[RERANKING] Scoring {len(hits)} hits...")
    cross_input = [[question, hit["content"]] for hit in hits]
    scores = CROSS_ENCODER_INSTANCE.predict(cross_input)
    
    for idx, hit in enumerate(hits):
        hit["cross_score"] = float(scores[idx])
        
    hits.sort(key=lambda x: x["cross_score"], reverse=True)
    return hits[:top_k]
