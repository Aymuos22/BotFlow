"""
Message ORM model.

Stores every message exchanged in a conversation: from the customer,
from the bot, from an agent, or system-generated.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_uuid

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class Message(Base):
    """
    A single message within a Conversation.

    Columns
    -------
    sender_type   : customer | bot | agent | system
    response_type : rag | fallback | handoff | manual
                    (null for customer messages)
    external_message_id: External provider message id for deduplication
    """

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=new_uuid, index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------ #
    # Message content
    # ------------------------------------------------------------------ #
    sender_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="customer | bot | agent | system",
    )
    message_text: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Raw message text"
    )
    normalized_text: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Normalized/transliterated text for search"
    )
    language: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="Detected language of this message"
    )
    response_type: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="rag | fallback | handoff | manual (for bot/agent messages)",
    )
    external_message_id: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        unique=True,
        comment="External provider id for deduplication (e.g. Twilio MessageSid)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # ------------------------------------------------------------------ #
    # Relationship
    # ------------------------------------------------------------------ #
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<Message id={self.id} sender={self.sender_type!r} "
            f"type={self.response_type!r}>"
        )
