"""
EvalResult ORM model.

One row per (eval_run, dataset_item) pair.  Stores:
  - What was retrieved (chunk/document IDs + scores)
  - What was generated (answer text)
  - Deterministic metrics (Recall@K, MRR, NDCG)
  - LLM-judge scores (faithfulness, correctness, relevance)
  - Failure type annotations
  - Timing

Append-only; never mutated after creation.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_uuid


class EvalResult(Base):
    """Per-example evaluation result inside a run."""

    __tablename__ = "eval_results"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("eval_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Dataset item identity ─────────────────────────────────────────── #
    dataset_item_id: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        comment="ID from the golden dataset YAML, e.g. factual_001",
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(
        String(60), nullable=True, comment="factual_lookup, multi_hop, adversarial, ..."
    )
    difficulty: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="easy | medium | hard"
    )
    language: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="english | hindi | hinglish"
    )
    answerable: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # ── Ground truth ─────────────────────────────────────────────────── #
    relevant_document_ids: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True, comment="Ground-truth relevant document UUIDs"
    )
    relevant_chunk_ids: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True, comment="Ground-truth relevant chunk IDs (doc_id-chunk-N)"
    )
    relevance_grades: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="chunk_id -> grade (0-3) for NDCG; binary assumed when absent",
    )

    # ── Retrieval results ─────────────────────────────────────────────── #
    retrieved_chunk_ids: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True, comment="Ordered list of retrieved chunk IDs"
    )
    retrieved_document_ids: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )
    retrieval_scores: Mapped[Optional[List[float]]] = mapped_column(
        JSON, nullable=True, comment="Weaviate scores, aligned with retrieved_chunk_ids"
    )
    search_mode: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="bm25 | hybrid"
    )

    # ── Deterministic retrieval metrics ───────────────────────────────── #
    recall_at_1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recall_at_3: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recall_at_5: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recall_at_10: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precision_at_1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precision_at_3: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precision_at_5: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mrr: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Reciprocal rank of first relevant result"
    )
    ndcg_at_5: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ndcg_at_10: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hit_rate_at_5: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="1.0 if any relevant result in top-5"
    )
    avg_retrieval_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Generation ───────────────────────────────────────────────────── #
    generated_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_type: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="rag | fallback"
    )
    fallback_triggered: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # ── Deterministic generation metrics ─────────────────────────────── #
    token_f1: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Token-level F1 vs expected_answer"
    )
    answer_length_chars: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ── LLM-judge scores ─────────────────────────────────────────────── #
    faithfulness_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="0-4 scale from LLM judge"
    )
    faithfulness_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    correctness_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    correctness_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    relevance_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    judge_model: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    judge_prompt_version: Mapped[Optional[str]] = mapped_column(
        String(40), nullable=True
    )
    judge_raw_response: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, comment="Full parsed judge JSON for audit"
    )

    # ── Failure taxonomy ─────────────────────────────────────────────── #
    failure_types: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of failure type strings from taxonomy, e.g. [wrong_chunk, incomplete_answer]",
    )

    # ── Latency ──────────────────────────────────────────────────────── #
    retrieval_latency_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    generation_latency_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    total_latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<EvalResult item={self.dataset_item_id!r} "
            f"recall@5={self.recall_at_5} faithful={self.faithfulness_score}>"
        )
