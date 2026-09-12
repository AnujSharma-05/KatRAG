from sqlalchemy.orm import Session
from .. import models
from ..milvus_store import milvus_store

def route_query(db_session: Session, query_vector: list[float], top_k: int = 3) -> list[str]:
    try:
        matches = milvus_store.search_categories(query_vector, top_k=top_k)
    except Exception as exc:
        print("Milvus search_categories failed:", exc)
        matches = []

    if not matches or matches[0]["score"] < 0.4:
        print("Router confidence low, skipping category filter. Global search initiated.")
        return []
    else:
        top_cats = [m["category_name"] for m in matches]
        print(f"Soft Routing to Top-{top_k} categories: {top_cats}")
        return top_cats
