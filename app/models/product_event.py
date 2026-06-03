"""
ProductEvent ORM model.

Append-only analytics ledger.  One row is written every time a product
appears in a RAG retrieval result ("retrieved") or in an actual LLM
answer ("suggested").  Never updated — only inserted and read.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_uuid

if TYPE_CHECKING:
    from app.models.product import Product


class ProductEvent(Base):
    """
    A single product analytics event.

    event_type:
        "retrieved" – product chunk appeared in Weaviate search results.
        "suggested" – RAG gave a real answer (not fallback) that included
                      this product's chunks.
    """

    __tablename__ = "product_events"
    __table_args__ = (
        Index("ix_product_events_product_created", "product_id", "created_at"),
        Index("ix_product_events_company_created", "company_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        index=True,
        comment="Null for portal (stateless) queries",
    )

    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="whatsapp",
        comment="whatsapp | portal",
    )
    event_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="retrieved | suggested",
    )
    query_text: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Original user query (for later analysis)"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ------------------------------------------------------------------ #
    # Relationships
    # ------------------------------------------------------------------ #
    product: Mapped["Product"] = relationship(
        "Product", back_populates="events", lazy="noload"
    )

    def __repr__(self) -> str:
        return (
            f"<ProductEvent id={self.id} product={self.product_id} "
            f"type={self.event_type!r} channel={self.channel!r}>"
        )
