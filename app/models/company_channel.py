"""
CompanyChannel ORM model.

Represents an inbound communication channel (e.g. a WhatsApp phone number)
associated with a company.

Constraints enforced here:
  - Only one primary channel per company per channel_type (enforced in service layer)
  - ``channel_type`` is currently restricted to ``whatsapp``
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_uuid

if TYPE_CHECKING:
    from app.models.company import Company


class CompanyChannel(Base):
    """
    A communication channel belonging to a company.

    Columns
    -------
    id           : UUID primary key
    company_id   : FK → companies.id
    channel_type : Currently always ``whatsapp``
    phone_number : E.164-formatted phone number
    session_name : Deterministic Twilio channel key (routing / portal display)
    is_primary   : True for the main channel (at most one per company+type)
    status       : active | inactive | pending
    created_at   : Row creation timestamp
    """

    __tablename__ = "company_channels"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="whatsapp",
        comment="whatsapp (only supported type in phase 1)",
    )
    phone_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="E.164-formatted phone number, e.g. +911234567890",
    )
    session_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Deterministic WhatsApp channel key (Twilio stack)",
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="At most one primary channel per company per channel_type",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending | active | inactive",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ------------------------------------------------------------------ #
    # Relationship
    # ------------------------------------------------------------------ #
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="channels",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<CompanyChannel id={self.id} phone={self.phone_number!r} "
            f"primary={self.is_primary}>"
        )
