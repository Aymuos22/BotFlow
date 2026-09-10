"""
EvalRun ORM model.

Represents a single execution of the evaluation framework against a dataset.
Immutable after completion; one run = one set of metrics.

Every run records the exact system configuration so results are reproducible
and regressions can be traced to a specific change.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_uuid


class EvalRun(Base):
    """
    One complete evaluation run.  Created at the start of a run, updated
    on completion (or failure).  Never updated for any other reason.
    """

    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    run_id: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        unique=True,
        index=True,
        comment="Human-readable ID, e.g. run_20260910_abc123",
    )

    # ── System configuration snapshot ────────────────────────────────── #
    dataset_version: Mapped[str] = mapped_column(
        String(40), nullable=False, comment="e.g. v1, v2"
    )
    embedding_model: Mapped[Optional[str]] = mapped_column(
        String(120), nullable=True, comment="e.g. voyage-3 or null for BM25-only"
    )
    retrieval_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="top_k, hybrid_alpha, score_threshold, confidence_strategy",
    )
    reranker_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="MMR lambda or null; extensible for neural rerankers",
    )
    llm_model: Mapped[Optional[str]] = mapped_column(
        String(120), nullable=True, comment="e.g. openai/gpt-oss-120b"
    )
    prompt_version: Mapped[Optional[str]] = mapped_column(
        String(40), nullable=True
    )
    judge_model: Mapped[Optional[str]] = mapped_column(
        String(120), nullable=True, comment="Model used for LLM-as-judge scoring"
    )
    judge_prompt_version: Mapped[Optional[str]] = mapped_column(
        String(40), nullable=True
    )
    git_commit: Mapped[Optional[str]] = mapped_column(
        String(60), nullable=True
    )
    experiment_name: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
        comment="Optional experiment tag, e.g. with_embeddings, baseline",
    )

    # ── Run status ────────────────────────────────────────────────────── #
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="running",
        comment="running | completed | failed",
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Aggregate metrics (populated on completion) ───────────────────── #
    total_examples: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    aggregate_metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Final aggregate: recall@k, mrr, ndcg, faithfulness, correctness, ...",
    )
    failure_counts: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Counts per failure type, e.g. {hallucination: 2, wrong_chunk: 5}",
    )

    # ── Timing ────────────────────────────────────────────────────────── #
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<EvalRun run_id={self.run_id!r} status={self.status!r}>"
