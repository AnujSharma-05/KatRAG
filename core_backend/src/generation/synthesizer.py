from ..llm_service import generate_answer

async def synthesize_answer(question: str, hits: list[dict], citations: list[dict], gate_decision: str, bypass_llm: bool = False) -> str:
    context_lines = [
        f"[Source {idx + 1}] (Page {cit.get('page_from', 'N/A')}, {cit.get('section_path', 'N/A')}): {hit['content']}" 
        for idx, (cit, hit) in enumerate(zip(citations, hits))
    ]
    context = "\n\n".join(context_lines)

    answer = await generate_answer(
        question=question,
        context=context,
        bypass_llm=bypass_llm,
    )
    
    if gate_decision == "HEDGED":
        answer = "Based on limited available documentation, " + answer
        
    return answer
