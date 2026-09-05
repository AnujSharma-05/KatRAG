import numpy as np
from sentence_transformers import CrossEncoder

# Initialize NLI model globally for efficient reuse
# We use cross-encoder/nli-deberta-v3-small as requested by the architecture.
nli_model = CrossEncoder('cross-encoder/nli-deberta-v3-small')

def verify_grounding(answer: str, retrieved_context: list[str]) -> float:
    """
    Natural Language Inference (NLI) Grounding Verifier.

    This mathematically scores whether the generated nswer is entailed by 
    the etrieved_context using a fast, local NLI model.

    Why NLI instead of LLM-as-a-judge?
    - Speed: NLI cross-encoders are significantly faster.
    - Determinism: LLMs evaluating themselves tend to correlate with their own failure modes.
      NLI provides an independent, mathematically verifiable entailment score.
    
    Args:
        answer: The generated answer from the LLM.
        retrieved_context: A list of context chunks retrieved from the vector store.
        
    Returns:
        float: A grounding score (0.0 to 1.0) indicating entailment confidence.
    """
    if not retrieved_context or not answer:
        return 0.0
        
    # Concatenate the retrieved context into a single premise string
    premise = " ".join(retrieved_context)
    
    # NLI model expects [premise, hypothesis]
    logits = nli_model.predict([premise, answer])
    
    # DeBERTa-v3 NLI output logits are typically mapped as:
    # 0: Contradiction
    # 1: Entailment
    # 2: Neutral
    
    # Apply softmax to get probabilities
    exp_scores = np.exp(logits - np.max(logits))
    probs = exp_scores / np.sum(exp_scores)
    
    # Return the probability of Entailment (index 1)
    entailment_prob = float(probs[1])
    
    return entailment_prob
