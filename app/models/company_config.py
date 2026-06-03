"""
CompanyConfig ORM model.

Stores all runtime-configurable settings for a company.
Changes here take effect immediately without redeployment.

JSON columns (fallback_config_json, handoff_config_json, etc.) are
stored as TEXT on SQLite and JSONB-compatible on PostgreSQL.

Future S3 readiness: document metadata rows will reference
``s3_bucket`` / ``s3_key`` columns in a separate ``documents`` table.
"""
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid
from app.core.secret_crypto import decrypt_secret, encrypt_secret

if TYPE_CHECKING:
    from app.models.company import Company


class CompanyConfig(Base, TimestampMixin):
    """
    Holds all per-company runtime configuration.

    One-to-one with Company.  All fields that control AI behaviour,
    RAG retrieval, language handling, or integrations live here so
    onboarding a new company never requires code changes or redeployment.
    """

    __tablename__ = "company_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # ------------------------------------------------------------------ #
    # Integration identifiers (deterministically generated from company_id)
    # ------------------------------------------------------------------ #
    weaviate_collection: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        comment="Deterministic Weaviate collection name for this company",
    )

    # ------------------------------------------------------------------ #
    # WhatsApp provider (Twilio | AiSensy | Meta Cloud API)
    # ------------------------------------------------------------------ #
    whatsapp_provider: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="twilio",
        comment="Active WhatsApp transport provider — twilio | aisensy | meta",
    )

    # ------------------------------------------------------------------ #
    # Twilio integration
    # ------------------------------------------------------------------ #
    twilio_whatsapp_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment=(
            "Per-company Twilio WhatsApp sender in whatsapp:+<E.164> format. "
            "Must be set per-company; no global fallback. "
            "Also used for inbound routing: maps the webhook 'To' field to this company."
        ),
    )

    twilio_account_sid: Mapped[Optional[str]] = mapped_column(
        String(80),
        nullable=True,
        comment=(
            "Optional per-company Twilio Account SID (ACxxxxxxxx…). "
            "When set, outbound sending and signature validation should use this "
            "No global fallback — must be configured via the portal."
        ),
    )

    _twilio_auth_token_encrypted: Mapped[Optional[str]] = mapped_column(
        "twilio_auth_token_encrypted",
        Text,
        nullable=True,
        comment=(
            "Encrypted per-company Twilio Auth Token (Fernet). "
            "Plaintext is not stored."
        ),
    )

    @property
    def twilio_auth_token(self) -> Optional[str]:
        return decrypt_secret(self._twilio_auth_token_encrypted)

    @twilio_auth_token.setter
    def twilio_auth_token(self, value: Optional[str]) -> None:
        self._twilio_auth_token_encrypted = encrypt_secret(value)

    @property
    def has_stored_twilio_auth_token(self) -> bool:
        """True when an encrypted auth token exists (no decryption)."""
        return bool(self._twilio_auth_token_encrypted)

    # ------------------------------------------------------------------ #
    # AiSensy integration (Project API + inbound webhooks)
    # ------------------------------------------------------------------ #
    aisensy_whatsapp_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment=(
            "WhatsApp Business number for this AiSensy project, in whatsapp:+<E.164> "
            "format. Used to map inbound webhook payloads to the tenant."
        ),
    )

    aisensy_project_id: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
        comment="AiSensy project id (Project API).",
    )

    _aisensy_api_key_encrypted: Mapped[Optional[str]] = mapped_column(
        "aisensy_api_key_encrypted",
        Text,
        nullable=True,
        comment="Encrypted AiSensy Project API key (Bearer).",
    )

    @property
    def aisensy_api_key(self) -> Optional[str]:
        return decrypt_secret(self._aisensy_api_key_encrypted)

    @aisensy_api_key.setter
    def aisensy_api_key(self, value: Optional[str]) -> None:
        self._aisensy_api_key_encrypted = encrypt_secret(value)

    @property
    def has_stored_aisensy_api_key(self) -> bool:
        return bool(self._aisensy_api_key_encrypted)

    # ------------------------------------------------------------------ #
    # Meta WhatsApp Cloud API (Graph)
    # ------------------------------------------------------------------ #
    meta_phone_number_id: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        comment=(
            "WhatsApp Business phone_number_id from Meta Developer / WABA "
            "(inbound webhook routing)."
        ),
    )

    meta_waba_id: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        comment=(
            "WhatsApp Business Account (WABA) id — used for template list/create API. "
            "Auto-resolved from phone_number_id if not set."
        ),
    )

    _meta_graph_access_token_encrypted: Mapped[Optional[str]] = mapped_column(
        "meta_graph_access_token_encrypted",
        Text,
        nullable=True,
        comment="Encrypted Graph API user access token (Bearer) for sending messages.",
    )

    _meta_app_secret_encrypted: Mapped[Optional[str]] = mapped_column(
        "meta_app_secret_encrypted",
        Text,
        nullable=True,
        comment=(
            "Encrypted Meta app secret — optional; enables X-Hub-Signature-256 verification."
        ),
    )

    _meta_webhook_verify_token_encrypted: Mapped[Optional[str]] = mapped_column(
        "meta_webhook_verify_token_encrypted",
        Text,
        nullable=True,
        comment="Encrypted verify_token for Meta webhook URL verification (GET).",
    )

    # ------------------------------------------------------------------ #
    # Google Sheets live sync
    # ------------------------------------------------------------------ #
    google_sheets_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="Mirror inbox conversations/messages to this company's Google Sheet.",
    )
    google_sheet_id: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="Google spreadsheet id used for live inbox/lead sync.",
    )
    google_sheet_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Human-friendly URL for the Google spreadsheet.",
    )

    @property
    def meta_graph_access_token(self) -> Optional[str]:
        return decrypt_secret(self._meta_graph_access_token_encrypted)

    @meta_graph_access_token.setter
    def meta_graph_access_token(self, value: Optional[str]) -> None:
        self._meta_graph_access_token_encrypted = encrypt_secret(value)

    @property
    def meta_app_secret(self) -> Optional[str]:
        return decrypt_secret(self._meta_app_secret_encrypted)

    @meta_app_secret.setter
    def meta_app_secret(self, value: Optional[str]) -> None:
        self._meta_app_secret_encrypted = encrypt_secret(value)

    @property
    def meta_webhook_verify_token(self) -> Optional[str]:
        return decrypt_secret(self._meta_webhook_verify_token_encrypted)

    @meta_webhook_verify_token.setter
    def meta_webhook_verify_token(self, value: Optional[str]) -> None:
        self._meta_webhook_verify_token_encrypted = encrypt_secret(value)

    @property
    def has_stored_meta_graph_token(self) -> bool:
        return bool(self._meta_graph_access_token_encrypted)

    @property
    def has_stored_meta_app_secret(self) -> bool:
        return bool(self._meta_app_secret_encrypted)

    @property
    def has_stored_meta_webhook_verify_token(self) -> bool:
        return bool(self._meta_webhook_verify_token_encrypted)

    handoff_staff_notify_whatsapp: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment=(
            "Supervisor WhatsApp (whatsapp:+E.164). On each *new* handoff, the API "
            "sends this number a short alert using the company's active WhatsApp provider."
        ),
    )

    # ------------------------------------------------------------------ #
    # Language settings
    # ------------------------------------------------------------------ #
    default_language: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="english",
        comment="english | hindi | hinglish",
    )
    supported_languages: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: ["english"],
        comment="Subset of [english, hindi, hinglish]",
    )

    # ------------------------------------------------------------------ #
    # AI / RAG settings
    # ------------------------------------------------------------------ #
    system_prompt: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="System-level instruction for the AI agent",
    )
    rag_config_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="RAG retrieval tuning parameters (top_k, score_threshold, etc.)",
    )

    # ------------------------------------------------------------------ #
    # Operational settings (all JSON for schema flexibility)
    # ------------------------------------------------------------------ #
    fallback_config_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Behaviour when the RAG pipeline cannot answer",
    )
    handoff_config_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Human handoff / escalation configuration",
    )
    business_hours_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Operating hours per timezone for out-of-hours handling",
    )

    # ------------------------------------------------------------------ #
    # WhatsApp behaviour
    # ------------------------------------------------------------------ #
    whatsapp_agent_inactivity_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment=(
            "When the business owner is chatting manually (agent mode), the bot "
            "auto-resumes after this many minutes of no agent messages. Null = use server default."
        ),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # ------------------------------------------------------------------ #
    # Relationship
    # ------------------------------------------------------------------ #
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="config",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<CompanyConfig id={self.id} company_id={self.company_id} "
            f"collection={self.weaviate_collection!r}>"
        )
