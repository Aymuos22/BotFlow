"""
Pydantic schemas for CompanyConfig.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import SUPPORTED_LANGUAGES
from app.utils.whatsapp_number import normalize_whatsapp_destination


class CompanyConfigBase(BaseModel):
    """Fields shared between create and update config schemas."""

    default_language: str = Field(
        default="english",
        description="Default conversation language",
    )
    supported_languages: List[str] = Field(
        default_factory=lambda: ["english"],
        description="Languages the bot can respond in",
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="System-level instruction injected into every AI request",
    )
    rag_config_json: Optional[Dict[str, Any]] = Field(
        default=None,
        description="RAG retrieval parameters (top_k, score_threshold, etc.)",
    )
    fallback_config_json: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Behaviour when the RAG pipeline cannot answer",
    )
    handoff_config_json: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Human handoff / escalation configuration",
    )
    business_hours_json: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Operating hours per timezone",
    )
    whatsapp_agent_inactivity_minutes: Optional[int] = Field(
        default=None,
        ge=0,
        le=24 * 60,
        description=(
            "When you manually message customers from the connected WhatsApp number, "
            "the bot pauses (agent mode). After this many minutes without any further "
            "agent messages, the bot automatically resumes. Null uses server default."
        ),
    )
    handoff_staff_notify_whatsapp: Optional[str] = Field(
        default=None,
        max_length=50,
        description=(
            "Supervisor WhatsApp for handoff alerts. Accepts +E.164, digits only, or "
            "whatsapp:+…; stored normalized as whatsapp:+<digits>."
        ),
    )

    google_sheets_enabled: Optional[bool] = Field(
        default=None,
        description="Mirror this company's inbox/messages to Google Sheets.",
    )
    google_sheet_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Existing Google spreadsheet id to use for live sync.",
    )

    @field_validator("supported_languages")
    @classmethod
    def validate_supported_languages(cls, v: List[str]) -> List[str]:
        invalid = [lang for lang in v if lang not in SUPPORTED_LANGUAGES]
        if invalid:
            raise ValueError(
                f"Unsupported languages: {invalid}. "
                f"Must be one of {SUPPORTED_LANGUAGES}"
            )
        if not v:
            raise ValueError("At least one language must be specified.")
        return v

    @field_validator("default_language")
    @classmethod
    def validate_default_language(cls, v: str) -> str:
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"default_language must be one of {SUPPORTED_LANGUAGES}"
            )
        return v

    @field_validator("handoff_staff_notify_whatsapp")
    @classmethod
    def validate_handoff_staff_notify_whatsapp(cls, v: Optional[str]) -> Optional[str]:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        try:
            return normalize_whatsapp_destination(v.strip())
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("google_sheet_id")
    @classmethod
    def validate_google_sheet_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        return v.strip()


class CompanyConfigCreate(CompanyConfigBase):
    """Internal schema used during onboarding (collection auto-generated)."""
    pass


class CompanyConfigUpdate(CompanyConfigBase):
    """Request body for PUT /companies/{id}/config – all fields optional."""
    default_language: Optional[str] = None  # type: ignore[assignment]
    supported_languages: Optional[List[str]] = None  # type: ignore[assignment]
    is_active: Optional[bool] = Field(
        default=None,
        description="Enable or disable this company's config (pauses the bot when False)",
    )
    whatsapp_agent_inactivity_minutes: Optional[int] = Field(  # type: ignore[assignment]
        default=None,
        ge=0,
        le=24 * 60,
        description=(
            "Auto-resume timeout (minutes) after manual (agent) messaging. "
            "Null uses server default."
        ),
    )
    whatsapp_provider: Optional[str] = Field(
        default=None,
        description="Active WhatsApp channel: twilio | aisensy | meta",
    )
    twilio_whatsapp_number: Optional[str] = Field(
        default=None,
        description=(
            "Twilio WhatsApp sender (whatsapp:+E.164). "
            "Use portal admin Twilio POST to store Account SID and auth token; "
            "this field can be set from the portal company config form."
        ),
    )
    google_sheets_enabled: Optional[bool] = None  # type: ignore[assignment]
    google_sheet_id: Optional[str] = None  # type: ignore[assignment]

    @field_validator("whatsapp_provider", mode="before")
    @classmethod
    def _normalize_whatsapp_provider(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if not isinstance(v, str):
            return v
        s = v.strip().lower()
        if s not in ("twilio", "aisensy", "meta"):
            raise ValueError(
                "whatsapp_provider must be 'twilio', 'aisensy', or 'meta'"
            )
        return s

    @field_validator("twilio_whatsapp_number", mode="before")
    @classmethod
    def _blank_twilio_number(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("twilio_whatsapp_number")
    @classmethod
    def _validate_twilio_number_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        if not s.startswith("whatsapp:"):
            raise ValueError("twilio_whatsapp_number must start with 'whatsapp:'")
        return s


class CompanyConfigRead(CompanyConfigBase):
    """Full config representation returned by read endpoints."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    company_id: uuid.UUID
    weaviate_collection: str
    whatsapp_provider: str
    twilio_whatsapp_number: Optional[str] = Field(
        default=None,
        description="Twilio WhatsApp sender (routing + outbound). Set via portal admin Twilio endpoint.",
    )
    twilio_account_sid: Optional[str] = Field(
        default=None,
        description="Twilio Account SID when configured.",
    )
    has_twilio_auth_token: bool = Field(
        default=False,
        validation_alias="has_stored_twilio_auth_token",
        description="True when an auth token is stored (never returned as plaintext).",
    )
    aisensy_whatsapp_number: Optional[str] = Field(
        default=None,
        description="AiSensy business WhatsApp number for webhook routing.",
    )
    aisensy_project_id: Optional[str] = Field(
        default=None,
        description="AiSensy project id (Project API).",
    )
    has_aisensy_api_key: bool = Field(
        default=False,
        validation_alias="has_stored_aisensy_api_key",
        description="True when an AiSensy API key is stored (never returned as plaintext).",
    )
    meta_phone_number_id: Optional[str] = Field(
        default=None,
        description="Meta WhatsApp Business phone_number_id (Cloud API routing).",
    )
    has_meta_graph_token: bool = Field(
        default=False,
        validation_alias="has_stored_meta_graph_token",
        description="True when a Graph API access token is stored.",
    )
    has_meta_app_secret: bool = Field(
        default=False,
        validation_alias="has_stored_meta_app_secret",
        description="True when Meta app secret is stored (signature verification).",
    )
    has_meta_webhook_verify_token: bool = Field(
        default=False,
        validation_alias="has_stored_meta_webhook_verify_token",
        description="True when webhook verify_token is stored.",
    )
    google_sheets_enabled: bool = Field(
        default=True,
        description="True when live Google Sheets sync is enabled for this company.",
    )
    google_sheet_id: Optional[str] = Field(
        default=None,
        description="Google spreadsheet id used for live sync.",
    )
    google_sheet_url: Optional[str] = Field(
        default=None,
        description="Google spreadsheet URL used for live sync.",
    )
    is_active: bool
    created_at: datetime
    updated_at: datetime
