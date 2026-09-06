import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.cache import query_cache, cosine_similarity

def test_cache_isolation():
    print("============================================================")
    print("CACHE SECURITY ISOLATION SUITE")
    print("============================================================")

    # Base payload and parameters
    org_a = "org_A"
    group_a = "group_1"
    
    org_b = "org_B"
    
    q1 = "What is the return policy?"
    # Using a dummy embedding, length 384 for example.
    # Semantically identical queries have high cosine similarity.
    emb1 = [0.1] * 384
    emb2 = [0.101] * 384 # slightly perturbed but highly similar
    
    payload = {"answer": "Return within 30 days.", "citations": []}
    as_of = None

    # Clean start
    query_cache.exact_store.clear()
    query_cache.semantic_store.clear()

    # Seed cache for Org A
    query_cache.set(org_a, group_a, q1, emb1, payload, as_of)
    print("Seeded cache for Org A.")

    # --- Test 1: Exact Hit ---
    res1 = query_cache.get(org_a, group_a, q1, emb1, as_of)
    assert res1 == payload, "Test 1 Failed: Expected Exact Hit"
    print("Test 1 (Exact Hit): PASS")

    # --- Test 2: Semantic Hit ---
    q2 = "What's the return window?"
    # emb2 is > 0.97 similar to emb1
    sim = cosine_similarity(emb1, emb2)
    assert sim >= 0.97, f"Sanity check failed, sim={sim}"
    
    res2 = query_cache.get(org_a, group_a, q2, emb2, as_of)
    assert res2 == payload, "Test 2 Failed: Expected Semantic Hit"
    print("Test 2 (Semantic Hit): PASS")

    # --- Test 3: P0 Security Isolation ---
    res3 = query_cache.get(org_b, group_a, q1, emb1, as_of)
    assert res3 is None, "Test 3 Failed: CRITICAL P0 LEAK! Org B saw Org A's cache!"
    print("Test 3 (P0 Security Isolation): PASS")

    # --- Test 4: Invalidation ---
    query_cache.invalidate_scope(org_a, group_a)
    res4 = query_cache.get(org_a, group_a, q1, emb1, as_of)
    assert res4 is None, "Test 4 Failed: Expected Cache Miss after invalidation"
    print("Test 4 (Invalidation): PASS")
    
    print("============================================================")
    print("ALL TESTS PASSED — SCOPED SEMANTIC CACHE VERIFIED")
    print("============================================================")

if __name__ == "__main__":
    test_cache_isolation()
