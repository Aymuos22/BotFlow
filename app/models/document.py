"""
Document ORM model.

Represents a file uploaded by a company admin for ingestion into the
RAG knowledge base.  The raw file lives in AWS S3; this table stores
only the metadata required for lookup, indexing, and auditing.

S3 key strategy:
    companies/{company_id}/documents/{document_id}/{sanitized_filename}

Status lifecycle:  uploaded → indexing → indexed → failed
"""
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.document_index_job import DocumentIndexJob


class Document(Base, TimestampMixin):
    """
    Metadata record for a company-owned document stored in AWS S3.

    The actual file bytes are NEVER stored in the database.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------ #
    # File metadata
    # ------------------------------------------------------------------ #
    file_name: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Original uploaded filename"
    )
    s3_bucket: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="S3 bucket name"
    )
    s3_key: Mapped[str] = mapped_column(
        String(1000), nullable=False, comment="Full S3 object key"
    )
    mime_type: Mapped[str] = mapped_column(
        String(200), nullable=False, default="application/octet-stream"
    )
    file_size: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="File size in bytes"
    )

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="uploaded",
        index=True,
        comment="uploaded | indexing | indexed | failed",
    )
    uploaded_by: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Identifier of who uploaded (email or system label)",
    )

    # ------------------------------------------------------------------ #
    # Relationships
    # ------------------------------------------------------------------ #
    company: Mapped["Company"] = relationship(
        "Company", foreign_keys=[company_id], lazy="noload"
    )
    index_jobs: Mapped[list["DocumentIndexJob"]] = relationship(
        "DocumentIndexJob",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<Document id={self.id} file={self.file_name!r} status={self.status!r}>"
        )
