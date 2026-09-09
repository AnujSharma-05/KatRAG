from typing import Optional
from pydantic import BaseModel, Field

class EvalQuestion(BaseModel):
    id: str
    query: str
    organization_id: str
    permitted_group_ids: list[str] = Field(default_factory=list)
    answerable: bool
    as_of: Optional[str] = None
    expected_category: Optional[str] = None
    relevant_document_ids: list[str] = Field(default_factory=list)
    relevant_chunk_ids: list[str] = Field(default_factory=list)
    gold_answer: str
    tags: list[str] = Field(default_factory=list)
