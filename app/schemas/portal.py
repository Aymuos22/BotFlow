"""Schemas for the portal HTTP API."""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import LanguageOptionRead

MAX_BCRYPT_PASSWORD_BYTES = 72


def _validate_bcrypt_password_bytes(password: str) -> str:
    if len(password.encode("utf-8")) > MAX_BCRYPT_PASSWORD_BYTES:
        raise ValueError("Password must be 72 bytes or fewer.")
    return password


class PortalChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=6000)


class PortalChatRequest(BaseModel):
    company_id: uuid.UUID
    message: str = Field(..., min_length=1, max_length=8000)
    history: Optional[List[PortalChatTurn]] = Field(
        None,
        max_length=24,
        description="Prior turns for multi-turn portal chat (same session).",
    )


class RagSourceItem(BaseModel):
    file_name: str
    document_id: Optional[str] = None
    chunk_index: Optional[int] = None
    score: Optional[float] = None


class PortalRecommendedProduct(BaseModel):
    name: str
    image_url: str
    image_alt: Optional[str] = None
    link: Optional[str] = None


class PortalChatResponse(BaseModel):
    answer: str
    response_type: str
    language: str
    detected_language: str
    top_score: Optional[float] = None
    sources: Optional[List[RagSourceItem]] = None
    recommended_products: Optional[List[PortalRecommendedProduct]] = None


class PortalCompanySummary(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str
    status: str


class PortalPromptConfigResponse(BaseModel):
    """System prompt and language settings (tenant-facing read)."""

    system_prompt: Optional[str] = None
    default_language: str
    supported_languages: List[str]


class PortalRagDefaultsResponse(BaseModel):
    """Server-wide defaults merged into RAG when company JSON omits keys."""

    score_threshold: float
    top_k: int
    hybrid_alpha: float
    rag_embeddings_enabled: bool
    rag_conversation_turns: int
    rag_augment_search_with_history: bool


class PortalRagConfigResponse(BaseModel):
    """Per-company ``rag_config_json`` plus effective global defaults."""

    rag_config_json: Optional[Dict[str, Any]] = None
    global_defaults: PortalRagDefaultsResponse


class PortalFallbackHandoffResponse(BaseModel):
    """Fallback copy and handoff / escalation JSON blobs."""

    fallback_config_json: Optional[Dict[str, Any]] = None
    handoff_config_json: Optional[Dict[str, Any]] = None
    business_hours_json: Optional[Dict[str, Any]] = None


class PortalIntegrationSummary(BaseModel):
    """Non-secret integration identifiers (read-only)."""

    weaviate_collection: str
    whatsapp_channel_key: Optional[str] = Field(
        default=None,
        description="Deterministic key on the primary WhatsApp channel, if present.",
    )
    whatsapp_provider: Optional[str] = Field(
        default=None,
        description="Active WhatsApp provider (twilio | aisensy | meta).",
    )
    twilio_whatsapp_number: Optional[str] = Field(
        default=None,
        description="Per-company Twilio WhatsApp number (whatsapp:+<E.164>) used for routing.",
    )
    twilio_account_sid: Optional[str] = Field(
        default=None,
        description="Twilio Account SID when set (helps verify UI saved credentials).",
    )
    has_twilio_auth_token: bool = Field(
        default=False,
        description="True when an auth token is stored. Never exposes the token.",
    )
    twilio_credentials_complete: bool = Field(
        default=False,
        description=(
            "True when WhatsApp number, Account SID, and auth token are all stored — "
            "required for outbound replies."
        ),
    )
    handoff_staff_notify_configured: bool = Field(
        default=False,
        description=(
            "True when handoff_staff_notify_whatsapp is set — each new handoff sends "
            "that number a WhatsApp alert using the company's Twilio sender."
        ),
    )
    twilio_credentials_save_path: str = Field(
        ...,
        description=(
            "POST here with X-Admin-Key and JSON body to save Twilio. "
            "PUT /companies/{id}/config does not accept Twilio secrets."
        ),
    )
    aisensy_whatsapp_number: Optional[str] = Field(
        default=None,
        description="AiSensy business WhatsApp number (whatsapp:+E.164) for webhook routing.",
    )
    aisensy_project_id: Optional[str] = Field(
        default=None,
        description="AiSensy project id (Project API).",
    )
    has_aisensy_api_key: bool = Field(
        default=False,
        description="True when a Project API key is stored (never returned as plaintext).",
    )
    aisensy_credentials_complete: bool = Field(
        default=False,
        description="True when business number, project id, and API key are stored.",
    )
    aisensy_credentials_save_path: str = Field(
        ...,
        description="POST here (admin) to save AiSensy integration fields.",
    )
    meta_phone_number_id: Optional[str] = Field(
        default=None,
        description="Meta Cloud API phone_number_id for webhook routing.",
    )
    meta_waba_id: Optional[str] = Field(
        default=None,
        description="WhatsApp Business Account id (for template API).",
    )
    has_meta_graph_token: bool = Field(
        default=False,
        description="True when a Graph API access token is stored.",
    )
    meta_credentials_complete: bool = Field(
        default=False,
        description="True when phone_number_id, access token, and verify_token are stored.",
    )
    meta_credentials_save_path: str = Field(
        ...,
        description="POST here (admin) to save Meta WhatsApp Cloud API fields.",
    )
    is_active: bool


class PortalConfigOverviewResponse(BaseModel):
    """Single payload to inspect prompt, RAG, escalation, and integration."""

    prompt: PortalPromptConfigResponse
    rag: PortalRagConfigResponse
    escalation: PortalFallbackHandoffResponse
    integration: PortalIntegrationSummary
    company_id: uuid.UUID
    updated_at: datetime
    language_catalog: List[LanguageOptionRead] = Field(
        description="All reply languages the backend accepts (for config UI).",
    )


class PortalUserPublic(BaseModel):
    id: uuid.UUID
    username: str
    role: Literal["admin", "user"]
    company_id: Optional[uuid.UUID] = None
    is_active: bool


class PortalAuthLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=150)
    password: str = Field(..., min_length=1, max_length=500)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, v: str) -> str:
        return _validate_bcrypt_password_bytes(v)


class PortalAuthLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: PortalUserPublic


class PortalBootstrapRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=150)
    password: str = Field(..., min_length=8, max_length=500)
    bootstrap_secret: str = Field(..., min_length=1, max_length=500)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, v: str) -> str:
        return _validate_bcrypt_password_bytes(v)


class PortalUserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=150)
    password: str = Field(..., min_length=8, max_length=500)
    role: Literal["admin", "user"]
    company_id: Optional[uuid.UUID] = None

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, v: str) -> str:
        return _validate_bcrypt_password_bytes(v)

    @model_validator(mode="after")
    def company_matches_role(self) -> "PortalUserCreateRequest":
        if self.role == "user" and self.company_id is None:
            raise ValueError("company_id is required for role user")
        if self.role == "admin" and self.company_id is not None:
            raise ValueError("company_id must be empty for role admin")
        return self


class PortalUserPasswordResetRequest(BaseModel):
    password: str = Field(..., min_length=8, max_length=500)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, v: str) -> str:
        return _validate_bcrypt_password_bytes(v)


class PortalTwilioConfigUpdateRequest(BaseModel):
    """
    Admin-only: store per-company Twilio credentials and WhatsApp number.

    Note: Auth token is accepted but never returned by any API.
    """

    twilio_whatsapp_number: str = Field(
        ...,
        min_length=6,
        max_length=50,
        description="Twilio WhatsApp number in whatsapp:+<E.164> format.",
        examples=["whatsapp:+14155238886"],
    )
    twilio_account_sid: str = Field(
        ...,
        min_length=10,
        max_length=80,
        description="Twilio Account SID (ACxxxxxxxx…).",
        examples=["ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"],
    )
    twilio_auth_token: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=500,
        description=(
            "Twilio Auth Token (stored encrypted). Omit, null, or empty to keep the "
            "existing token when updating number or SID only."
        ),
    )
    enable_twilio_provider: bool = Field(
        default=True,
        description="If true, sets whatsapp_provider=twilio for this company.",
    )

    @field_validator("twilio_auth_token", mode="before")
    @classmethod
    def _blank_auth_token_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class PortalTwilioConfigUpdateResponse(BaseModel):
    company_id: uuid.UUID
    whatsapp_provider: str
    twilio_whatsapp_number: Optional[str] = None
    twilio_account_sid: Optional[str] = None
    has_twilio_auth_token: bool = False
    webhook_path: str = Field(
        default="/api/v1/webhooks/twilio/messages",
        description="Configure this path as the Twilio WhatsApp webhook URL (POST).",
    )


class PortalAisensyConfigUpdateRequest(BaseModel):
    """Admin-only: store AiSensy Project API credentials and routing number."""

    aisensy_whatsapp_number: str = Field(
        ...,
        min_length=6,
        max_length=50,
        description="Business WhatsApp number in whatsapp:+<E.164> format.",
        examples=["whatsapp:+918888888888"],
    )
    aisensy_project_id: str = Field(
        ...,
        min_length=2,
        max_length=120,
        description="Project id from the AiSensy dashboard (Project API).",
    )
    aisensy_api_key: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=500,
        description=(
            "Project API key (Bearer token). Omit or empty to keep the existing key "
            "when updating number or project id only."
        ),
    )
    enable_aisensy_provider: bool = Field(
        default=True,
        description="If true, sets whatsapp_provider=aisensy for this company.",
    )

    @field_validator("aisensy_api_key", mode="before")
    @classmethod
    def _blank_api_key_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class PortalAisensyConfigUpdateResponse(BaseModel):
    company_id: uuid.UUID
    whatsapp_provider: str
    aisensy_whatsapp_number: Optional[str] = None
    aisensy_project_id: Optional[str] = None
    has_aisensy_api_key: bool = False
    webhook_path: str = Field(
        default="/api/v1/webhooks/aisensy/messages",
        description="Configure this URL in AiSensy Project webhooks (POST JSON).",
    )


class PortalMetaWhatsappConfigUpdateRequest(BaseModel):
    """Admin-only: Meta WhatsApp Cloud API (Graph) credentials."""

    meta_phone_number_id: str = Field(
        ...,
        min_length=4,
        max_length=32,
        description="WhatsApp phone_number_id from Meta Business / Developer console.",
        examples=["123456789012345"],
    )
    meta_waba_id: Optional[str] = Field(
        default=None,
        min_length=4,
        max_length=32,
        description=(
            "WhatsApp Business Account id (optional but recommended — used for template "
            "list/create. If omitted the system auto-resolves it via Graph API)."
        ),
        examples=["1348185130513488"],
    )
    meta_graph_access_token: Optional[str] = Field(
        default=None,
        min_length=20,
        max_length=2048,
        description=(
            "Long-lived Graph API user access token with whatsapp_business_messaging. "
            "Omit to keep existing token."
        ),
    )
    meta_app_secret: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=500,
        description="Meta App secret — enables X-Hub-Signature-256 verification. Omit to keep.",
    )
    meta_webhook_verify_token: Optional[str] = Field(
        default=None,
        min_length=4,
        max_length=500,
        description=(
            "Custom string for Meta webhook URL verification (GET). Omit to keep existing."
        ),
    )
    enable_meta_provider: bool = Field(
        default=True,
        description="If true, sets whatsapp_provider=meta for this company.",
    )

    @field_validator(
        "meta_graph_access_token",
        "meta_app_secret",
        "meta_webhook_verify_token",
        mode="before",
    )
    @classmethod
    def _blank_secrets_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class PortalMetaWhatsappConfigUpdateResponse(BaseModel):
    company_id: uuid.UUID
    whatsapp_provider: str
    meta_phone_number_id: Optional[str] = None
    meta_waba_id: Optional[str] = None
    has_meta_graph_token: bool = False
    has_meta_app_secret: bool = False
    has_meta_webhook_verify_token: bool = False
    webhook_get_post_path: str = Field(
        default="/api/v1/webhooks/meta/whatsapp",
        description="Subscribe in Meta App > WhatsApp > Configuration (GET verify + POST).",
    )
