import hashlib
import json
import math
from typing import Optional


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


class ScopedQueryCache:
    def __init__(self):
        # In-memory mock for Redis
        # exact_store maps key -> response dict
        self.exact_store = {}
        # semantic_store maps scope_prefix -> list of dicts: {'query': str, 'embedding': list, 'response': dict, 'as_of': str}
        self.semantic_store = {}

    def _get_scope_prefix(self, org_id: str, group_id: str) -> str:
        return f"katrag:{org_id}:{group_id}"

    def generate_exact_key(self, org_id: str, group_id: str, query: str, as_of: Optional[str]) -> str:
        raw_str = query + str(as_of)
        hash_digest = hashlib.sha256(raw_str.encode('utf-8')).hexdigest()
        scope = self._get_scope_prefix(org_id, group_id)
        return f"{scope}:exact:{hash_digest}"

    def get(self, org_id: str, group_id: str, query: str, query_embedding: list[float], as_of: Optional[str]) -> dict | None:
        exact_key = self.generate_exact_key(org_id, group_id, query, as_of)
        
        # 1. Exact Hit
        if exact_key in self.exact_store:
            return self.exact_store[exact_key]
            
        # 2. Semantic Hit
        scope = self._get_scope_prefix(org_id, group_id)
        if scope in self.semantic_store:
            for item in self.semantic_store[scope]:
                if str(item['as_of']) == str(as_of):
                    sim = cosine_similarity(query_embedding, item['embedding'])
                    if sim >= 0.97:
                        return item['response']
                        
        return None

    def set(self, org_id: str, group_id: str, query: str, query_embedding: list[float], response: dict, as_of: Optional[str]):
        exact_key = self.generate_exact_key(org_id, group_id, query, as_of)
        scope = self._get_scope_prefix(org_id, group_id)
        
        # Store exact
        self.exact_store[exact_key] = response
        
        # Store semantic
        if scope not in self.semantic_store:
            self.semantic_store[scope] = []
            
        self.semantic_store[scope].append({
            'query': query,
            'embedding': query_embedding,
            'response': response,
            'as_of': str(as_of)
        })

    def invalidate_scope(self, org_id: str, group_id: str):
        scope = self._get_scope_prefix(org_id, group_id)
        
        # Delete semantic
        if scope in self.semantic_store:
            del self.semantic_store[scope]
            
        # Delete exact
        keys_to_delete = [k for k in self.exact_store.keys() if k.startswith(f"{scope}:")]
        for k in keys_to_delete:
            del self.exact_store[k]

# Global cache singleton
query_cache = ScopedQueryCache()
