"""WhatsApp template campaigns, follow-up rules, outbox, and suppression."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid


class WhatsAppCampaign(Base, TimestampMixin):
    __tablename__ = "whatsapp_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", index=True,
        comment="draft | running | paused | completed | cancelled",
    )
    template_name: Mapped[str] = mapped_column(String(200), nullable=False)
    language_code: Mapped[str] = mapped_column(String(20), nullable=False, default="en")
    body_variable_mappings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    header_media_url_mapping: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    total_recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queued_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class WhatsAppCampaignRecipient(Base, TimestampMixin):
    __tablename__ = "whatsapp_campaign_recipients"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("whatsapp_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    phone_number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    raw_phone: Mapped[str] = mapped_column(String(100), nullable=False)
    row_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued", index=True,
        comment="queued | sent | failed | skipped | suppressed",
    )
    outbox_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class WhatsAppFollowupRule(Base, TimestampMixin):
    __tablename__ = "whatsapp_followup_rules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    steps_json: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list,
        comment="Up to 3 template steps with delay_minutes/template/language/variables/header_media_url.",
    )


class WhatsAppOutboxJob(Base, TimestampMixin):
    __tablename__ = "whatsapp_outbox_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="campaign | followup")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued", index=True,
        comment="queued | sending | sent | failed | skipped | suppressed | cancelled",
    )
    to_number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    template_name: Mapped[str] = mapped_column(String(200), nullable=False)
    language_code: Mapped[str] = mapped_column(String(20), nullable=False, default="en")
    body_variables_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    header_media_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("whatsapp_campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )
    recipient_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("whatsapp_campaign_recipients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    followup_rule_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("whatsapp_followup_rules.id", ondelete="SET NULL"), nullable=True, index=True
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    followup_step_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class WhatsAppSuppression(Base, TimestampMixin):
    __tablename__ = "whatsapp_suppressions"
    __table_args__ = (
        UniqueConstraint("company_id", "phone_number", name="uq_whatsapp_suppression_company_phone"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    phone_number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(50), nullable=False, default="opt_out")
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="whatsapp")
    suppressed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
