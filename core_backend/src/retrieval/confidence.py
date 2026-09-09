import math

def sigmoid(x):
    return 1 / (1 + math.exp(-x))

def evaluate_confidence(hits: list[dict]) -> str:
    if not hits:
        return "REFUSE"
    
    for hit in hits:
        hit["prob_relevant"] = sigmoid(hit.get("cross_score", 0.0))
        
    top_prob = hits[0]["prob_relevant"] if hits else 0.0
    gate_decision = "ANSWER"
    
    if top_prob < 0.35:
        gate_decision = "REFUSE"
    elif top_prob < 0.70:
        gate_decision = "HEDGED"
        
    return gate_decision
