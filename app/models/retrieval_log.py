"""
RetrievalLog ORM model.

Immutable audit log for every RAG retrieval attempt.  Used for:
  - Performance monitoring
  - Quality analysis of RAG responses
  - Fallback / handoff rate tracking
  - Future model fine-tuning data
"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_uuid


class RetrievalLog(Base):
    """
    One RAG retrieval event, including query, results, and decisions.
    Records are append-only and never updated.
    """

    __tablename__ = "retrieval_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ------------------------------------------------------------------ #
    # Query details
    # ------------------------------------------------------------------ #
    query_text: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Original customer query"
    )
    normalized_query: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Normalized query sent to Weaviate"
    )
    detected_language: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    weaviate_collection: Mapped[str] = mapped_column(
        String(300), nullable=False
    )

    # ------------------------------------------------------------------ #
    # Retrieval results
    # ------------------------------------------------------------------ #
    top_k: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    top_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Highest relevance score from Weaviate"
    )
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_result_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, comment="Full Weaviate search result for debugging"
    )

    # ------------------------------------------------------------------ #
    # Decision flags
    # ------------------------------------------------------------------ #
    fallback_triggered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    handoff_triggered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<RetrievalLog id={self.id} score={self.top_score} "
            f"fallback={self.fallback_triggered}>"
        )
