import math

def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    if not relevant_ids:
        return 1.0 # If nothing is relevant, recall is perfect
    top_k = retrieved_ids[:k]
    hits = sum(1 for rid in relevant_ids if rid in top_k)
    return hits / len(relevant_ids)

def mrr(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    if not relevant_ids:
        return 1.0
    for rank, rid in enumerate(retrieved_ids):
        if rid in relevant_ids:
            return 1.0 / (rank + 1)
    return 0.0

def ndcg_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    if not relevant_ids:
        return 1.0
    
    dcg = 0.0
    for rank, rid in enumerate(retrieved_ids[:k]):
        if rid in relevant_ids:
            dcg += 1.0 / math.log2(rank + 2)
            
    idcg = 0.0
    for rank in range(min(k, len(relevant_ids))):
        idcg += 1.0 / math.log2(rank + 2)
        
    return dcg / idcg if idcg > 0 else 0.0

def false_refusal_rate(decisions: list[str], ground_truth_answerability: list[bool]) -> float:
    # decision == "REFUSE" when ground_truth_answerability == True
    answerable_count = sum(1 for ans in ground_truth_answerability if ans)
    if answerable_count == 0:
        return 0.0
    false_refusals = sum(1 for d, ans in zip(decisions, ground_truth_answerability) if ans and d == "REFUSE")
    return false_refusals / answerable_count

def false_answer_rate(decisions: list[str], ground_truth_answerability: list[bool]) -> float:
    # decision != "REFUSE" when ground_truth_answerability == False
    unanswerable_count = sum(1 for ans in ground_truth_answerability if not ans)
    if unanswerable_count == 0:
        return 0.0
    false_answers = sum(1 for d, ans in zip(decisions, ground_truth_answerability) if not ans and d != "REFUSE")
    return false_answers / unanswerable_count
