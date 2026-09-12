def reciprocal_rank_fusion(*lists_of_hits, k=60):
    fused_scores = {}
    hit_map = {}
    
    for hit_list in lists_of_hits:
        for rank, hit in enumerate(hit_list):
            doc_id = hit["document_id"]
            chunk_idx = hit["chunk_index"]
            key = f"{doc_id}_{chunk_idx}"
            
            if key not in hit_map:
                hit_map[key] = hit
                fused_scores[key] = 0.0
                
            fused_scores[key] += 1.0 / (k + rank + 1)
            
    sorted_keys = sorted(fused_scores.keys(), key=lambda k: fused_scores[k], reverse=True)
    
    fused_hits = []
    for key in sorted_keys:
        hit = hit_map[key].copy()
        hit["score"] = fused_scores[key]
        fused_hits.append(hit)
        
    return fused_hits
