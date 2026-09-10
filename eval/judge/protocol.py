"""
JudgeProtocol — the interface that any LLM judge must satisfy.

Design: provider-agnostic.  The default implementation (LLMJudge) uses the
existing ``LLMClientProtocol`` from the application so no new provider
credentials are needed.  A different judge (e.g. GPT-4o, Claude) can be
injected by implementing this protocol.

Output schema
-------------
Every judge call returns a ``JudgeOutput`` containing three ``ScoreDimension``
objects (faithfulness, correctness, relevance).  All fields are validated with
Pydantic so malformed LLM output is caught early and surfaced as a structured
error rather than a silent None.
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────── #
# Output schema (validated with Pydantic)
# ─────────────────────────────────────────────────────────────────────────── #


class ScoreDimension(BaseModel):
    """
    One evaluated dimension from the judge.

    score:        Integer 0–4 (see SCORE_LABELS in config.py for rubric).
    reason:       Free-text explanation of the score.
    failure_type: Optional failure taxonomy string if the score is low (< 3).
    """

    score: int = Field(..., ge=0, le=4)
    reason: str
    failure_type: Optional[str] = None

    @field_validator("score", mode="before")
    @classmethod
    def coerce_score(cls, v: object) -> int:
        """Accept string scores like '3' or float scores like 3.0."""
        try:
            return int(float(str(v)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"score must be an integer 0-4, got {v!r}") from exc

    @property
    def normalised(self) -> float:
        """Score as a 0.0–1.0 float."""
        return self.score / 4.0


class JudgeOutput(BaseModel):
    """
    Complete output from one judge evaluation call.

    All three dimensions are required.  The model is intentionally strict:
    if the LLM returns malformed JSON, Pydantic raises a ``ValidationError``
    so the caller can retry or record a failed judge call rather than silently
    propagating a None.
    """

    faithfulness: ScoreDimension
    correctness: ScoreDimension
    relevance: ScoreDimension

    judge_model: Optional[str] = None
    prompt_version: Optional[str] = None

    @property
    def mean_score(self) -> float:
        """Average of the three dimension scores (normalised 0–1)."""
        return (
            self.faithfulness.normalised
            + self.correctness.normalised
            + self.relevance.normalised
        ) / 3.0

    def to_dict(self) -> dict:
        return {
            "faithfulness": {
                "score": self.faithfulness.score,
                "normalised": self.faithfulness.normalised,
                "reason": self.faithfulness.reason,
                "failure_type": self.faithfulness.failure_type,
            },
            "correctness": {
                "score": self.correctness.score,
                "normalised": self.correctness.normalised,
                "reason": self.correctness.reason,
                "failure_type": self.correctness.failure_type,
            },
            "relevance": {
                "score": self.relevance.score,
                "normalised": self.relevance.normalised,
                "reason": self.relevance.reason,
                "failure_type": self.relevance.failure_type,
            },
            "mean_score": self.mean_score,
            "judge_model": self.judge_model,
            "prompt_version": self.prompt_version,
        }


# ─────────────────────────────────────────────────────────────────────────── #
# Judge protocol
# ─────────────────────────────────────────────────────────────────────────── #


@runtime_checkable
class JudgeProtocol(Protocol):
    """Interface that any LLM judge implementation must satisfy."""

    async def evaluate(
        self,
        *,
        question: str,
        retrieved_context: str,
        generated_answer: str,
        expected_answer: Optional[str] = None,
    ) -> JudgeOutput:
        """
        Evaluate a single RAG example.

        Args:
            question:           The user question.
            retrieved_context:  The context that was passed to the RAG LLM.
            generated_answer:   The answer produced by the RAG pipeline.
            expected_answer:    Ground-truth answer (may be None).

        Returns:
            ``JudgeOutput`` with validated scores.

        Raises:
            ``JudgeError`` on unrecoverable failure (e.g. all retries exhausted).
        """
        ...


class JudgeError(Exception):
    """Raised when the judge cannot produce a valid output after all retries."""

    def __init__(self, message: str, last_raw_response: Optional[str] = None) -> None:
        super().__init__(message)
        self.last_raw_response = last_raw_response
