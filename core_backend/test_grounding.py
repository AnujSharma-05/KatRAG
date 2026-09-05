import sys
import os

# Ensure src is importable
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.grounding import verify_grounding

def run_tests():
    context = ["We offer a generous 30-day return policy for all items purchased in-store or online. Items must be returned in their original condition."]
    
    print("Running NLI Grounding Verification Tests...\n")
    
    # Test Case 1: Grounded
    answer_grounded = "You have 30 days to return the item."
    print(f"Context: {context[0]}")
    print(f"Answer (Grounded): {answer_grounded}")
    score_1 = verify_grounding(answer_grounded, context)
    print(f"Entailment Score: {score_1:.4f}")
    
    if score_1 > 0.80:
        print("=> Test Case 1: PASS\n")
    else:
        print("=> Test Case 1: FAIL (Score too low)\n")
        
    # Test Case 2: Hallucinated
    answer_hallucinated = "You have 90 days to return the item and get a free gift."
    print(f"Answer (Hallucinated): {answer_hallucinated}")
    score_2 = verify_grounding(answer_hallucinated, context)
    print(f"Entailment Score: {score_2:.4f}")
    
    if score_2 < 0.40:
        print("=> Test Case 2: PASS\n")
    else:
        print("=> Test Case 2: FAIL (Score too high)\n")

if __name__ == "__main__":
    run_tests()
