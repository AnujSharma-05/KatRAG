import hashlib
import json
import math
import os
from typing import Optional
import redis

# Initialize Redis client
redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.Redis.from_url(redis_url, decode_responses=True)

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)

class ScopedQueryCache:
    def __init__(self):
        pass

    def _get_scope_prefix(self, org_id: str, group_id: str) -> str:
        return f"katrag:{org_id}:{group_id}"

    def generate_exact_key(self, org_id: str, group_id: str, query: str, as_of: Optional[str], doc_set_version: Optional[str] = None) -> str:
        version_part = doc_set_version or ""
        raw_str = query + str(as_of) + version_part
        hash_digest = hashlib.sha256(raw_str.encode('utf-8')).hexdigest()
        scope = self._get_scope_prefix(org_id, group_id)
        return f"{scope}:exact:{hash_digest}"

    def get(self, org_id: str, group_id: str, query: str, query_embedding: list[float], as_of: Optional[str], doc_set_version: Optional[str] = None) -> dict | None:
        exact_key = self.generate_exact_key(org_id, group_id, query, as_of, doc_set_version)
        # Exact hit
        exact_val = redis_client.get(exact_key)
        if exact_val:
            return json.loads(exact_val)
        # Semantic hit
        scope = self._get_scope_prefix(org_id, group_id)
        semantic_list_key = f"{scope}:semantic:{doc_set_version or ''}"
        items = redis_client.lrange(semantic_list_key, 0, -1)
        for item_str in items:
            item = json.loads(item_str)
            if str(item.get('as_of')) == str(as_of):
                sim = cosine_similarity(query_embedding, item['embedding'])
                if sim >= 0.97:
                    return item['response']
        return None

    def set(self, org_id: str, group_id: str, query: str, query_embedding: list[float], response: dict, as_of: Optional[str], doc_set_version: Optional[str] = None):
        exact_key = self.generate_exact_key(org_id, group_id, query, as_of, doc_set_version)
        scope = self._get_scope_prefix(org_id, group_id)
        # Store exact
        redis_client.set(exact_key, json.dumps(response), ex=86400)
        # Store semantic
        semantic_list_key = f"{scope}:semantic:{doc_set_version or ''}"
        semantic_item = {
            'query': query,
            'embedding': query_embedding,
            'response': response,
            'as_of': str(as_of)
        }
        redis_client.lpush(semantic_list_key, json.dumps(semantic_item))
        redis_client.expire(semantic_list_key, 86400)

    def invalidate_scope(self, org_id: str, group_id: str):
        scope = self._get_scope_prefix(org_id, group_id)
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(cursor=cursor, match=f"{scope}:*", count=100)
            if keys:
                redis_client.delete(*keys)
            if cursor == 0:
                break

# Global cache singleton
query_cache = ScopedQueryCache()
