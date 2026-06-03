"""
DocumentIndexJob ORM model.

Tracks the DB-backed job for parsing a document and indexing its chunks
into Weaviate.  Since Redis is not used, all job state is persisted here.

Status lifecycle:  pending → processing → completed | failed

Retry logic:  retry_count < settings.indexing_max_retries to re-queue.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_uuid

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.document import Document


class DocumentIndexJob(Base):
    """
    One indexing attempt for a document.

    Multiple rows can exist for the same document (retries), but at
    most one should be in ``processing`` state at a time.
    """

    __tablename__ = "document_index_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------ #
    # Job state
    # ------------------------------------------------------------------ #
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="pending | processing | completed | failed",
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    from sqlalchemy import func
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ------------------------------------------------------------------ #
    # Relationships
    # ------------------------------------------------------------------ #
    company: Mapped["Company"] = relationship(
        "Company", foreign_keys=[company_id], lazy="noload"
    )
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="index_jobs",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentIndexJob id={self.id} doc={self.document_id} "
            f"status={self.status!r} retry={self.retry_count}>"
        )
