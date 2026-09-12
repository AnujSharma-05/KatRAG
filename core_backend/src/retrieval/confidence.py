import math
import json
import os
import logging

CALIBRATION_FILE = os.path.join(os.path.dirname(__file__), "calibration_weights.json")
try:
    with open(CALIBRATION_FILE, "r") as f:
        weights = json.load(f)
        A = weights.get("A", 1.0)
        B = weights.get("B", 0.0)
except FileNotFoundError:
    logging.warning("SEVERE: calibration_weights.json not found! Falling back to uncalibrated heuristic (A=1.0, B=0.0)")
    A = 1.0
    B = 0.0

def platt_scaling(score):
    return 1 / (1 + math.exp(-(A * score + B)))

def evaluate_confidence(hits: list[dict]) -> str:
    if not hits:
        return "REFUSE"
    
    for hit in hits:
        hit["prob_relevant"] = platt_scaling(hit.get("cross_score", 0.0))
        
    top_prob = hits[0]["prob_relevant"] if hits else 0.0
    gate_decision = "ANSWER"
    
    if top_prob < 0.35:
        gate_decision = "REFUSE"
    elif top_prob < 0.70:
        gate_decision = "HEDGED"
        
    return gate_decision
