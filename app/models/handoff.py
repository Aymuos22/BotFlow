"""
Handoff ORM model.

Tracks a human-escalation request within a conversation.

Status lifecycle
----------------
requested → assigned (when agent picks up) → active → resolved
                                           ↘ cancelled (if customer leaves)

When a handoff is requested, the parent Conversation's
``current_mode`` is set to ``"agent"`` so the bot stops auto-replying.
Resolving the handoff does NOT automatically resume the bot – the
operator must explicitly call the resume-bot API. This is deliberate:
a human agent may want to add a closing note before handing back.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.conversation import Conversation


class Handoff(Base, TimestampMixin):
    """One escalation event within a conversation."""

    __tablename__ = "handoffs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------ #
    # Trigger metadata
    # ------------------------------------------------------------------ #
    requested_by: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="system",
        comment="system | customer | agent",
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable reason (keyword detected, low-confidence, etc.)",
    )

    # ------------------------------------------------------------------ #
    # Assignment
    # ------------------------------------------------------------------ #
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="requested",
        index=True,
        comment="requested | assigned | active | resolved | cancelled",
    )
    assigned_agent_id: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )

    # ------------------------------------------------------------------ #
    # Resolution
    # ------------------------------------------------------------------ #
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ------------------------------------------------------------------ #
    # Relationships
    # ------------------------------------------------------------------ #
    company: Mapped["Company"] = relationship(
        "Company", foreign_keys=[company_id], lazy="noload"
    )
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", foreign_keys=[conversation_id], lazy="noload"
    )

    def __repr__(self) -> str:
        return (
            f"<Handoff id={self.id} status={self.status!r} "
            f"reason={self.reason!r}>"
        )
