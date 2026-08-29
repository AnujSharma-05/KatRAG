import yaml
import time
import requests
from pathlib import Path

# Adjust this URL to point to your Python Core Engine
API_URL = "http://localhost:8000/api/v1/chat" 

def run_evals():
    dataset_path = Path(__file__).parent / "eval_dataset.yaml"
    with open(dataset_path, "r") as f:
        queries = yaml.safe_load(f)

    total = len(queries)
    answered_correctly = 0
    false_refusals = 0
    true_refusals = 0
    
    print(f"Running evals for {total} queries...\n")
    
    for q in queries:
        start_time = time.time()
        
        # Simulating the payload you currently send to your API
        payload = {
            "query": q["query"],
            "group_id": q["group_id"]
        }
        
        try:
            response = requests.post(API_URL, json=payload)
            response_data = response.json()
            latency = time.time() - start_time
            
            # Simple heuristic check for this baseline
            # Assuming your API returns an error or specific string when it refuses to answer
            is_refusal = "I don't know" in response_data.get("answer", "") or response.status_code != 200
            
            if q["answerable"]:
                if is_refusal:
                    false_refusals += 1
                    print(f"❌ False Refusal: {q['query']} ({latency:.2f}s)")
                else:
                    answered_correctly += 1
                    print(f"✅ Success: {q['query']} ({latency:.2f}s)")
            else:
                if is_refusal:
                    true_refusals += 1
                    print(f"✅ True Refusal: {q['query']} ({latency:.2f}s)")
                else:
                    print(f"❌ Hallucination (Answered unanswerable): {q['query']} ({latency:.2f}s)")
                    
        except Exception as e:
            print(f"⚠️ Error on {q['query']}: {e}")

    # Metrics
    frr = false_refusals / sum(1 for q in queries if q["answerable"]) if sum(1 for q in queries if q["answerable"]) > 0 else 0
    
    print("\n--- Eval Results ---")
    print(f"Answered correctly: {answered_correctly}")
    print(f"False Refusal Rate (FRR): {frr:.0%}")
    print(f"True Refusal Rate: {true_refusals}/{sum(1 for q in queries if not q['answerable'])}")

if __name__ == "__main__":
    run_evals()