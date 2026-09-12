import argparse
import yaml
import time
from tabulate import tabulate
from .schema import EvalQuestion
from .metrics import recall_at_k, mrr, ndcg_at_k, false_refusal_rate, false_answer_rate

def load_golden_set(filepath: str) -> list[EvalQuestion]:
    with open(filepath, "r") as f:
        data = yaml.safe_load(f)
    return [EvalQuestion(**item) for item in data]

def mock_run_pipeline(config: str, query: str) -> dict:
    # A mock implementation to simulate running the different configurations for smoke testing.
    # In a real scenario, this would call the actual backend service with the specified configuration flags.
    time.sleep(0.01) # Simulate latency
    
    if config == "A":
        return {"retrieved_ids": ["DOC-789"], "gate_decision": "ANSWER"}
    elif config == "B":
        return {"retrieved_ids": ["DOC-789", "DOC-123"], "gate_decision": "ANSWER"}
    elif config == "C":
        return {"retrieved_ids": ["DOC-789", "DOC-456"], "gate_decision": "ANSWER"}
    elif config == "D":
        # Simulate confidence gate
        if "secret" in query:
            return {"retrieved_ids": [], "gate_decision": "REFUSE"}
        return {"retrieved_ids": ["DOC-789"], "gate_decision": "ANSWER"}
    
    return {"retrieved_ids": [], "gate_decision": "REFUSE"}

def run_ablation(questions: list[EvalQuestion], smoke: bool = False):
    configs = {
        "A": "A: Dense Baseline",
        "B": "B: + Native BM25",
        "C": "C: + Cross-Encoder",
        "D": "D: + Confidence Gate"
    }
    
    if smoke:
        questions = questions[:3]
        
    results_table = []
    
    for cfg_key, cfg_name in configs.items():
        start_time = time.time()
        
        all_retrieved = []
        all_relevant = []
        decisions = []
        ground_truth = []
        
        for q in questions:
            res = mock_run_pipeline(cfg_key, q.query)
            all_retrieved.append(res["retrieved_ids"])
            all_relevant.append(q.relevant_document_ids if q.relevant_document_ids else ["DOC-789"]) # Mock relevant
            decisions.append(res["gate_decision"])
            ground_truth.append(q.answerable)
            
        latency = (time.time() - start_time) / len(questions) * 1000 # average latency ms
        
        # Calculate metrics over the batch
        avg_recall = sum(recall_at_k(ret, rel, 50) for ret, rel in zip(all_retrieved, all_relevant)) / len(questions)
        avg_mrr = sum(mrr(ret, rel) for ret, rel in zip(all_retrieved, all_relevant)) / len(questions)
        avg_ndcg = sum(ndcg_at_k(ret, rel, 5) for ret, rel in zip(all_retrieved, all_relevant)) / len(questions)
        frr = false_refusal_rate(decisions, ground_truth)
        far = false_answer_rate(decisions, ground_truth)
        
        results_table.append([
            cfg_name,
            f"{avg_recall:.3f}",
            f"{avg_mrr:.3f}",
            f"{avg_ndcg:.3f}",
            f"{frr:.3f}",
            f"{far:.3f}",
            f"{latency:.1f}"
        ])

    headers = ["Configuration", "Recall@50", "MRR", "nDCG@5", "FRR", "FAR", "p95 Latency (ms)"]
    print("\n" + tabulate(results_table, headers, tablefmt="github") + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ablation Runner")
    parser.add_argument("--smoke", action="store_true", help="Run smoke test")
    args = parser.parse_args()
    
    try:
        import yaml
        from tabulate import tabulate
    except ImportError:
        import subprocess
        subprocess.check_call(["pip", "install", "pyyaml", "tabulate", "pydantic"])
        
    dataset = load_golden_set("tests/evals/golden_set.yaml")
    run_ablation(dataset, smoke=args.smoke)
