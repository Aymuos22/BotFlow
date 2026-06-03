"""
Conversation ORM model.

Represents a WhatsApp conversation thread between a customer phone
number and a company's bot/agent.

current_mode lifecycle:
    bot  →  agent  (after human handoff triggered)
    agent →  bot   (when agent releases conversation)
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.message import Message


class Conversation(Base, TimestampMixin):
    """
    One ongoing or closed conversation between a customer and a company.

    A conversation is keyed by (company_id, customer_phone) so the same
    customer phoning two companies creates two separate conversations.
    """

    __tablename__ = "conversations"

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
    # Customer identity
    # ------------------------------------------------------------------ #
    customer_phone: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="Normalized E.164 phone number of the customer",
    )

    # ------------------------------------------------------------------ #
    # Conversation state
    # ------------------------------------------------------------------ #
    current_mode: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="bot",
        comment="bot | agent – controls auto-reply behaviour",
    )
    status: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="active",
        comment="active | closed",
    )
    detected_language: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment=(
            "english | hindi | hinglish – last decisive customer language "
            "(short/ambiguous messages keep the previous value)"
        ),
    )
    assigned_agent_id: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Identifier of the human agent (future use)",
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of the most recent message",
    )

    # ------------------------------------------------------------------ #
    # Inbox / CRM (set from company dashboard)
    # ------------------------------------------------------------------ #
    lead_warmth: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="hot | warm | cold — lead temperature for follow-up",
    )
    inquiry_complete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Customer inquiry marked complete on dashboard",
    )
    inquiry_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When inquiry was marked complete",
    )
    lead_warmth_locked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Set true when lead_warmth is edited in portal; AI classification skips",
    )
    lead_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Stored AI summary of the customer's need for CRM and Google Sheets.",
    )
    lead_summary_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When lead_summary was last generated from customer messages.",
    )

    # ------------------------------------------------------------------ #
    # Bot / spam protection
    # ------------------------------------------------------------------ #
    is_blocked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True when the sender has been identified as a bot or spammer",
    )
    block_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable reason this conversation was blocked",
    )

    # ------------------------------------------------------------------ #
    # Opt-out (user requested no more messages)
    # ------------------------------------------------------------------ #
    opted_out: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True when the customer requested to stop receiving messages",
    )
    opted_out_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the customer opted out",
    )

    # ------------------------------------------------------------------ #
    # Relationships
    # ------------------------------------------------------------------ #
    company: Mapped["Company"] = relationship(
        "Company", foreign_keys=[company_id], lazy="noload"
    )
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<Conversation id={self.id} phone={self.customer_phone!r} "
            f"mode={self.current_mode!r}>"
        )
