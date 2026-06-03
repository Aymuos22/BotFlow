"""Schemas for WhatsApp campaigns, follow-ups, and outbox."""
import re
import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class CampaignPreviewResponse(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    total_rows: int
    valid_rows: int
    invalid_rows: int
    errors: list[str] = []


class CampaignCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    template_name: str = Field(..., min_length=1, max_length=200)
    language_code: str = Field(default="en", min_length=2, max_length=20)
    phone_column: str = Field(..., min_length=1, max_length=200)
    body_variable_mappings: list[Any] = Field(default_factory=list)
    header_media_url_mapping: Optional[str] = None
    rows: list[dict[str, Any]] = Field(default_factory=list)


class CampaignRead(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    status: str
    template_name: str
    language_code: str
    body_variable_mappings: list[Any]
    header_media_url_mapping: Optional[str] = None
    total_recipients: int
    queued_count: int
    sent_count: int
    failed_count: int
    skipped_count: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CampaignRecipientRead(BaseModel):
    id: uuid.UUID
    row_index: int
    phone_number: str
    raw_phone: str
    row_json: dict[str, Any]
    status: str
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class CampaignDetail(CampaignRead):
    recipients: list[CampaignRecipientRead] = []
    outbox_counts: dict[str, int] = {}


class CampaignActionRequest(BaseModel):
    action: str = Field(..., pattern="^(start|pause|cancel|retry_failed)$")


class FollowupStep(BaseModel):
    delay_minutes: int = Field(..., ge=1, le=60 * 24 * 90)
    template_name: str = Field(..., min_length=1, max_length=200)
    language_code: str = Field(default="en", min_length=2, max_length=20)
    body_variables: list[str] = Field(default_factory=list)
    header_media_url: Optional[str] = None


class FollowupRuleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    is_active: bool = True
    steps: list[FollowupStep] = Field(..., min_length=1, max_length=3)


class FollowupRuleUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    is_active: Optional[bool] = None
    steps: Optional[list[FollowupStep]] = Field(default=None, min_length=1, max_length=3)


class FollowupRuleRead(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    is_active: bool
    steps_json: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OutboxJobRead(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    kind: str
    status: str
    to_number: str
    template_name: str
    language_code: str
    body_variables_json: list[Any]
    header_media_url: Optional[str] = None
    campaign_id: Optional[uuid.UUID] = None
    followup_rule_id: Optional[uuid.UUID] = None
    conversation_id: Optional[uuid.UUID] = None
    attempts: int
    next_attempt_at: datetime
    sent_at: Optional[datetime] = None
    provider_message_id: Optional[str] = None
    last_error: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TemplateRead(BaseModel):
    name: str
    language: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    components: list[dict[str, Any]] = []


class MetaTemplateCreateRequest(BaseModel):
    """
    Submit a new TEXT-only Meta template (utility/marketing).

    Meta reviews before APPROVED; editing approved wording requires a new submission.
    """

    name: str = Field(..., min_length=1, max_length=512)
    category: Literal["utility", "marketing"] = "utility"
    language: str = Field(..., min_length=2, max_length=32)
    body_text: str = Field(..., min_length=1, max_length=5500)
    footer_text: Optional[str] = Field(default=None, max_length=60)
    header_text: Optional[str] = Field(default=None, max_length=60)
    body_example_values: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def meta_template_name_slug(cls, v: str) -> str:
        s = v.strip().lower()
        if not re.fullmatch(r"[a-z0-9_]+", s):
            raise ValueError(
                "Template name must use lowercase letters, digits, and underscores only."
            )
        return s

    @field_validator("language")
    @classmethod
    def meta_language_trim(cls, v: str) -> str:
        return v.strip()


class QuickSendRequest(BaseModel):
    """
    One-shot bulk send: submit a Meta template AND create a campaign in a single call.

    The campaign starts automatically once Meta approves the template
    (the outbox worker polls approval every ~60 s and launches it).

    ``template_name`` must be lowercase letters/digits/underscores (Meta requirement).
    If the template already exists and is APPROVED, the campaign starts immediately.
    """

    campaign_name: str = Field(..., min_length=1, max_length=200)
    template_name: str = Field(..., min_length=1, max_length=200)
    template_body: str = Field(..., min_length=1, max_length=5500)
    template_header: Optional[str] = Field(default=None, max_length=60)
    template_footer: Optional[str] = Field(default=None, max_length=60)
    language_code: str = Field(default="en", min_length=2, max_length=20)
    category: Literal["utility", "marketing"] = "marketing"
    phone_column: str = Field(default="phone", min_length=1, max_length=200)
    rows: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("template_name")
    @classmethod
    def _slug(cls, v: str) -> str:
        s = v.strip().lower()
        if not re.fullmatch(r"[a-z0-9_]+", s):
            raise ValueError("template_name must use lowercase letters, digits, and underscores only.")
        return s


class QuickSendResponse(BaseModel):
    campaign_id: uuid.UUID
    campaign_status: str
    template_name: str
    template_status: str
    message: str
