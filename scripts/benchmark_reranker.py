import os
import sys
import time
import numpy as np
from tabulate import tabulate

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

from tests.evals.ablation_runner import load_golden_set
from tests.evals.metrics import recall_at_k, ndcg_at_k
from core_backend.src.retrieval.reranker import rerank_hits

def run_benchmark():
    dataset = load_golden_set('tests/evals/golden_set.yaml')
    
    top_k_candidates = [15]
    results = []
    
    print('Running Cross-Encoder Benchmark Sweep...')
    
    # Silence the reranker prints
    import sys, io
    
    for k in top_k_candidates:
        latencies = []
        all_retrieved = []
        all_relevant = []
        
        for q in dataset:
            hits = []
            relevant_id = 'DOC-789'
            if hasattr(q, 'relevant_document_ids') and q.relevant_document_ids:
                relevant_id = q.relevant_document_ids[0]
            
            dummy_text = 'This is a random document context that does not contain the answer. ' * 30
            
            for i in range(k):
                is_relevant = (i == (k // 2))
                doc_id = relevant_id if is_relevant else f'DOC-RANDOM-{i}'
                content_text = (q.gold_answer or 'Relevant stuff') + ' ' * 100 if is_relevant else dummy_text
                hits.append({
                    'document_id': doc_id,
                    'chunk_index': i,
                    'content': content_text
                })
            
            pre_rerank_ids = [h['document_id'] for h in hits]
            
            # suppress stdout
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            
            start_time = time.time()
            reranked_hits = rerank_hits(q.query, hits, top_k=5)
            latency_ms = (time.time() - start_time) * 1000
            
            sys.stdout = old_stdout
            
            latencies.append(latency_ms)
            
            post_rerank_ids = [h['document_id'] for h in reranked_hits]
            
            all_retrieved.append({'pre': pre_rerank_ids, 'post': post_rerank_ids})
            all_relevant.append([relevant_id])
            
        p95_latency = np.percentile(latencies, 95)
        
        avg_recall = sum(recall_at_k(ret['pre'], rel, k) for ret, rel in zip(all_retrieved, all_relevant)) / len(dataset)
        avg_ndcg = sum(ndcg_at_k(ret['post'], rel, 5) for ret, rel in zip(all_retrieved, all_relevant)) / len(dataset)
        
        results.append([
            k,
            f'{avg_recall:.3f}',
            f'{avg_ndcg:.3f}',
            f'{p95_latency:.1f}'
        ])
        
    headers = ['Candidate Count', 'Recall@K (pre-rerank)', 'nDCG@5 (post-rerank)', 'p95 Latency (ms)']
    print('\n' + tabulate(results, headers, tablefmt='github') + '\n')

if __name__ == '__main__':
    run_benchmark()
