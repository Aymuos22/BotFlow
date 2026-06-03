"""
Product ORM model.

Represents a company's product/service entry in the knowledge base.
Products are indexed into Weaviate for semantic search alongside documents,
and tracked individually for analytics (how often retrieved / suggested).
"""
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.product_event import ProductEvent


class Product(Base, TimestampMixin):
    """
    A single product or service offered by a company.

    The ``description`` field (plus name/category/attributes) is used to
    generate a searchable text chunk that is embedded into Weaviate.
    ``weaviate_indexed`` tracks whether the current DB values are in sync
    with the Weaviate collection.
    """

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("company_id", "sku", name="uq_products_company_sku"),
    )

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
    # Core fields
    # ------------------------------------------------------------------ #
    name: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Human-readable product name"
    )
    sku: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        index=True,
        comment="Stock-keeping unit; unique per company when set",
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Full product description – this text gets embedded for RAG",
    )

    # ------------------------------------------------------------------ #
    # Flexible structured data
    # ------------------------------------------------------------------ #
    price_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment='e.g. {"amount": 999, "currency": "INR", "unit": "per month"}',
    )
    attributes_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Arbitrary key-value product attributes (color, size, warranty …)",
    )
    synonyms_json: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default="[]",
        comment="Search synonyms and alternate names for this product.",
    )

    @property
    def synonyms(self) -> List[str]:
        return list(self.synonyms_json or [])

    @synonyms.setter
    def synonyms(self, value: List[str]) -> None:
        self.synonyms_json = list(value or [])

    # ------------------------------------------------------------------ #
    # Lifecycle / sync state
    # ------------------------------------------------------------------ #
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )
    weaviate_indexed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True when current DB values are present in Weaviate",
    )

    # ------------------------------------------------------------------ #
    # Relationships
    # ------------------------------------------------------------------ #
    company: Mapped["Company"] = relationship(
        "Company", foreign_keys=[company_id], lazy="noload"
    )
    events: Mapped[List["ProductEvent"]] = relationship(
        "ProductEvent",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<Product id={self.id} name={self.name!r} "
            f"company={self.company_id} indexed={self.weaviate_indexed}>"
        )
