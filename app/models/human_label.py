"""
HumanLabel ORM model.

Stores human annotations for a subset of EvalResult rows.

Purpose: calibrate the LLM judge by comparing its scores against human
judgement.  Calculate agreement statistics (accuracy, precision, recall, F1,
Pearson correlation) to determine whether the judge is trustworthy.

One EvalResult may have labels from multiple labelers to compute inter-annotator
agreement.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_uuid


class HumanLabel(Base):
    """One human annotation for one evaluated example."""

    __tablename__ = "human_labels"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    eval_result_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("eval_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Labeler identity ──────────────────────────────────────────────── #
    labeler_id: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        comment="Email, username, or opaque ID of the human annotator",
    )

    # ── Scores (0–4 scale matching the LLM judge rubric) ──────────────── #
    correctness: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="0=completely wrong, 1=mostly wrong, 2=partial, 3=mostly correct, 4=fully correct",
    )
    faithfulness: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="0=completely hallucinated, 4=fully grounded in context",
    )
    relevance: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="0=completely irrelevant, 4=directly answers the question",
    )

    # ── Optional free-text notes ──────────────────────────────────────── #
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Qualitative annotation: what was wrong, what was right",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<HumanLabel labeler={self.labeler_id!r} "
            f"correct={self.correctness} faithful={self.faithfulness}>"
        )
