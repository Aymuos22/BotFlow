"""
Pydantic schemas for the LLM integration layer.
"""
from typing import List, Optional
from pydantic import BaseModel


class LLMRequest(BaseModel):
    """Structured input to the LLM generate call."""
    context_chunks: List[str]
    user_query: str
    system_prompt: Optional[str] = None
    output_language: str = "english"
    model: Optional[str] = None


class LLMResponse(BaseModel):
    """Structured output from the LLM generate call."""
    answer: str
    model_used: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
