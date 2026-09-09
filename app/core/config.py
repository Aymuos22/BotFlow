"""
Application settings and configuration management.

Architecture decision: Only global secrets and infrastructure URLs live in
environment variables. All company-specific configuration is stored in the
database to enable zero-deployment onboarding of new tenants.
"""
import json
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_async_database_url(url: str) -> str:
    """Use asyncpg for bare Postgres URLs (e.g. Supabase URI paste defaults to psycopg2)."""
    if "sqlite" in url:
        return url
    scheme = url.split("://", 1)[0] if "://" in url else ""
    if "+" in scheme:
        return url
    lower = url.lower()
    if lower.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.split("://", 1)[1]
    if lower.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.split("://", 1)[1]
    return url


class Settings(BaseSettings):
    """
    Global application settings loaded from environment variables / .env file.

    Per our multi-tenant architecture contract:
      - Global infra URLs (Weaviate, DB) → env vars / secrets manager
      - Company-specific config (prompts, RAG settings, Twilio) → database
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Application
    # ------------------------------------------------------------------ #
    app_name: str = Field(default="BotFlow", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")
    # Public base URL used to construct absolute URLs (e.g. product image URLs)
    # served from the /static/ mount.  Set to the externally reachable origin of
    # this API server, e.g. https://api.yourdomain.com or http://<ec2-ip>:8000.
    public_base_url: str = Field(
        default="http://localhost:8000",
        alias="PUBLIC_BASE_URL",
    )
    expose_internal_error_detail: bool = Field(
        default=False,
        alias="EXPOSE_INTERNAL_ERROR_DETAIL",
        description="If true, INTERNAL_ERROR responses include exception text (even when DEBUG=false).",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ------------------------------------------------------------------ #
    # Database (Supabase Postgres / SQLite for local)
    # ------------------------------------------------------------------ #
    database_url: str = Field(
        default="sqlite+aiosqlite:///./botflow_dev.db",
        alias="DATABASE_URL",
    )
    db_echo: bool = Field(default=False, alias="DB_ECHO")

    @field_validator(
        "debug",
        "expose_internal_error_detail",
        "db_echo",
        "google_sheets_sync_enabled",
        "google_sheets_create_spreadsheets",
        mode="before",
    )
    @classmethod
    def _coerce_bool_like_env(cls, v: object) -> object:
        if isinstance(v, str):
            raw = v.strip().lower()
            if raw in {"release", "prod", "production"}:
                return False
        return v

    @field_validator("database_url", mode="before")
    @classmethod
    def _coerce_postgres_to_asyncpg(cls, v: object) -> object:
        if isinstance(v, str):
            return _normalize_async_database_url(v)
        return v
    db_pool_size: int = Field(default=2, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=1, alias="DB_MAX_OVERFLOW")
    db_pool_recycle_seconds: int = Field(
        default=300,
        alias="DB_POOL_RECYCLE_SECONDS",
        description="Recycle idle connections after this many seconds to avoid PgBouncer evictions.",
    )

    # ------------------------------------------------------------------ #
    # Google Sheets live sync
    # ------------------------------------------------------------------ #
    google_sheets_sync_enabled: bool = Field(
        default=True,
        alias="GOOGLE_SHEETS_SYNC_ENABLED",
        description=(
            "When true and service-account credentials are configured, company "
            "inbox conversations/messages are mirrored to per-company Google Sheets."
        ),
    )
    google_service_account_json: Optional[str] = Field(
        default=None,
        alias="GOOGLE_SERVICE_ACCOUNT_JSON",
        description="Raw Google service-account JSON for Sheets API access.",
    )
    google_service_account_file: Optional[str] = Field(
        default=None,
        alias="GOOGLE_SERVICE_ACCOUNT_FILE",
        description="Path to a Google service-account JSON file.",
    )
    google_oauth_client_json: Optional[str] = Field(
        default=None,
        alias="GOOGLE_OAUTH_CLIENT_JSON",
        description="Raw Google OAuth web/installed client JSON.",
    )
    google_oauth_client_file: Optional[str] = Field(
        default=None,
        alias="GOOGLE_OAUTH_CLIENT_FILE",
        description="Path to a Google OAuth web/installed client JSON file.",
    )
    google_oauth_refresh_token: Optional[str] = Field(
        default=None,
        alias="GOOGLE_OAUTH_REFRESH_TOKEN",
        description="Refresh token for the Google account used to write Sheets.",
    )
    google_sheets_create_spreadsheets: bool = Field(
        default=True,
        alias="GOOGLE_SHEETS_CREATE_SPREADSHEETS",
        description="Create a spreadsheet for companies that do not yet have one.",
    )
    google_sheets_timeout_seconds: int = Field(
        default=20,
        alias="GOOGLE_SHEETS_TIMEOUT_SECONDS",
    )
    google_sheets_retry_base_seconds: int = Field(
        default=60,
        alias="GOOGLE_SHEETS_RETRY_BASE_SECONDS",
    )
    google_sheets_retry_max_attempts: int = Field(
        default=8,
        alias="GOOGLE_SHEETS_RETRY_MAX_ATTEMPTS",
    )
    google_sheets_retry_batch_size: int = Field(
        default=10,
        alias="GOOGLE_SHEETS_RETRY_BATCH_SIZE",
    )

    # ------------------------------------------------------------------ #
    # WhatsApp campaigns / follow-up outbox
    # ------------------------------------------------------------------ #
    whatsapp_outbox_retry_base_seconds: int = Field(
        default=120,
        alias="WHATSAPP_OUTBOX_RETRY_BASE_SECONDS",
    )
    whatsapp_outbox_retry_max_attempts: int = Field(
        default=6,
        alias="WHATSAPP_OUTBOX_RETRY_MAX_ATTEMPTS",
    )
    whatsapp_outbox_batch_size: int = Field(
        default=20,
        alias="WHATSAPP_OUTBOX_BATCH_SIZE",
    )
    whatsapp_outbox_poll_seconds: int = Field(
        default=10,
        alias="WHATSAPP_OUTBOX_POLL_SECONDS",
    )
    whatsapp_outbox_company_delay_seconds: float = Field(
        default=3.0,
        alias="WHATSAPP_OUTBOX_COMPANY_DELAY_SECONDS",
        description="Conservative per-company pacing between Meta template sends.",
    )
    whatsapp_followup_session_hours: float = Field(
        default=24.0,
        alias="WHATSAPP_FOLLOWUP_SESSION_HOURS",
        ge=1.0,
        le=72.0,
        description=(
            "Hours after the customer's last message during which open-lead follow-ups "
            "may be sent as AI session text instead of Meta templates."
        ),
    )

    # ------------------------------------------------------------------ #
    # Twilio WhatsApp Integration
    # Credentials (Account SID, Auth Token, WhatsApp number) are stored
    # per-company in CompanyConfig — no global fallback.
    # ------------------------------------------------------------------ #
    twilio_timeout_seconds: int = Field(
        default=30,
        alias="TWILIO_TIMEOUT_SECONDS",
    )
    twilio_validate_signature: bool = Field(
        default=False,
        alias="TWILIO_VALIDATE_SIGNATURE",
        description=(
            "If true, validate X-Twilio-Signature on incoming webhook requests "
            "using the per-company Auth Token stored in CompanyConfig."
        ),
    )

    # ------------------------------------------------------------------ #
    # AiSensy WhatsApp (Project API)
    # Per-company project id + API key live in CompanyConfig. Base URL and
    # send path may vary by AiSensy API version — override via env if needed.
    # ------------------------------------------------------------------ #
    aisensy_api_base_url: str = Field(
        default="https://api.aisensy.com",
        alias="AISENSY_API_BASE_URL",
    )
    aisensy_send_text_path: str = Field(
        default="/project-apis/v1/whatsapp-messages",
        alias="AISENSY_SEND_TEXT_PATH",
        description=(
            "HTTP path appended to AISENSY_API_BASE_URL for outbound session text. "
            "Confirm against AiSensy Project API (Stoplight) for your account."
        ),
    )
    aisensy_timeout_seconds: int = Field(
        default=30,
        alias="AISENSY_TIMEOUT_SECONDS",
    )

    # ------------------------------------------------------------------ #
    # Meta WhatsApp Cloud API (Graph) — per-company tokens in CompanyConfig
    # ------------------------------------------------------------------ #
    meta_graph_api_base_url: str = Field(
        default="https://graph.facebook.com",
        alias="META_GRAPH_API_BASE_URL",
    )
    meta_graph_api_version: str = Field(
        default="v21.0",
        alias="META_GRAPH_API_VERSION",
        description="Graph API version segment, e.g. v21.0",
    )
    meta_webhook_timeout_seconds: int = Field(
        default=30,
        alias="META_WEBHOOK_TIMEOUT_SECONDS",
    )
    whatsapp_audio_transcription_enabled: bool = Field(
        default=True,
        alias="WHATSAPP_AUDIO_TRANSCRIPTION_ENABLED",
    )
    whatsapp_audio_transcription_model: str = Field(
        default="gpt-4o-mini-transcribe",
        alias="WHATSAPP_AUDIO_TRANSCRIPTION_MODEL",
        description="OpenAI transcription model (used when OPENAI_API_KEY is set). Groq Whisper is used as automatic fallback.",
    )
    whatsapp_audio_max_bytes: int = Field(
        default=15_000_000,
        alias="WHATSAPP_AUDIO_MAX_BYTES",
    )
    meta_webhook_verify_token: Optional[str] = Field(
        default=None,
        alias="META_WEBHOOK_VERIFY_TOKEN",
        description=(
            "Optional global verify_token for Meta webhook GET. When set, matches "
            "hub.verify_token without reading per-company DB (single-app installs)."
        ),
    )

    # ------------------------------------------------------------------ #
    # BotFlow voice-call webhook
    # ------------------------------------------------------------------ #
    botflow_webhook_secret: Optional[str] = Field(
        default=None,
        alias="BOTFLOW_WEBHOOK_SECRET",
        description=(
            "HMAC-SHA256 secret for verifying X-Webhook-Signature from BotFlow "
            "post-call webhooks. When set, requests with an invalid or missing "
            "signature are rejected with 401."
        ),
    )

    # ------------------------------------------------------------------ #
    # Weaviate Vector DB
    # ------------------------------------------------------------------ #
    weaviate_url: str = Field(
        default="http://localhost:8080", alias="WEAVIATE_URL"
    )
    weaviate_api_key: Optional[str] = Field(default=None, alias="WEAVIATE_API_KEY")
    weaviate_timeout_seconds: int = Field(
        default=30, alias="WEAVIATE_TIMEOUT_SECONDS"
    )

    # ------------------------------------------------------------------ #
    # Supabase Storage – document file storage (replaces AWS S3)
    # ------------------------------------------------------------------ #
    supabase_url: str = Field(
        default="",
        alias="SUPABASE_URL",
        description="Supabase project URL, e.g. https://xxxx.supabase.co",
    )
    supabase_service_role_key: str = Field(
        default="",
        alias="SUPABASE_SERVICE_ROLE_KEY",
        description="Supabase service-role key (secret) for backend storage operations.",
    )
    supabase_storage_bucket: str = Field(
        default="documents",
        alias="SUPABASE_STORAGE_BUCKET",
        description="Supabase Storage bucket name where uploaded documents are stored.",
    )

    # ------------------------------------------------------------------ #
    # LLM — provider: groq | openai  (default: groq)
    # ------------------------------------------------------------------ #
    llm_provider: str = Field(
        default="groq",
        alias="LLM_PROVIDER",
        description="groq | openai — which backend get_llm_client() wires up",
    )
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    llm_model: str = Field(
        default="openai/gpt-oss-120b",
        alias="LLM_MODEL",
    )
    llm_timeout_seconds: int = Field(default=60, alias="LLM_TIMEOUT_SECONDS")
    llm_temperature: float = Field(default=1.0, alias="LLM_TEMPERATURE")
    llm_max_completion_tokens: int = Field(
        default=1024,
        alias="LLM_MAX_COMPLETION_TOKENS",
        description="Groq free tier: keep low so prompt+completion stays under TPM limits.",
    )
    llm_max_context_chars: int = Field(
        default=12000,
        alias="LLM_MAX_CONTEXT_CHARS",
        description="Max characters of joined RAG chunks sent to the LLM (truncated if larger).",
    )
    llm_max_system_chars: int = Field(
        default=6000,
        alias="LLM_MAX_SYSTEM_CHARS",
        description="Max characters of system prompt + language hint (per-company prompts).",
    )
    llm_top_p: float = Field(default=1.0, alias="LLM_TOP_P")
    llm_reasoning_effort: Optional[str] = Field(
        default=None,
        alias="LLM_REASONING_EFFORT",
        description="Groq-only for reasoning models (low|medium|high); omit on free tier to save TPM.",
    )
    llm_stream: bool = Field(
        default=False,
        alias="LLM_STREAM",
        description="Groq: use streaming API and aggregate chunks (matches CLI-style streaming)",
    )

    # ------------------------------------------------------------------ #
    # RAG / Indexing
    # ------------------------------------------------------------------ #
    rag_score_threshold: float = Field(default=0.4, alias="RAG_SCORE_THRESHOLD")
    rag_top_k: int = Field(default=5, alias="RAG_TOP_K")
    rag_hybrid_alpha: float = Field(
        default=0.5,
        alias="RAG_HYBRID_ALPHA",
        description="Weaviate hybrid fusion: 0=BM25 only, 1=vector only (when embeddings on).",
    )
    rag_conversation_turns: int = Field(
        default=5,
        alias="RAG_CONVERSATION_TURNS",
        description="Max prior messages (WhatsApp) to pass as conversation context.",
    )
    rag_augment_search_with_history: bool = Field(
        default=True,
        alias="RAG_AUGMENT_SEARCH_WITH_HISTORY",
        description="Append recent conversation text to the retrieval query for follow-ups.",
    )
    rag_embeddings_enabled: bool = Field(
        default=False,
        alias="RAG_EMBEDDINGS_ENABLED",
        description="If true, embed chunks at index time and run Weaviate hybrid search.",
    )
    embedding_provider: str = Field(
        default="voyage",
        alias="EMBEDDING_PROVIDER",
        description="Embedding backend: voyage (VoyageAI) or openai.",
    )
    embedding_model: str = Field(
        default="voyage-3",
        alias="EMBEDDING_MODEL",
        description="VoyageAI model name, e.g. voyage-3 or voyage-3-lite.",
    )
    voyage_api_key: Optional[str] = Field(
        default=None,
        alias="VOYAGE_API_KEY",
        description="VoyageAI API key for embedding generation.",
    )
    embedding_api_key: Optional[str] = Field(
        default=None,
        alias="EMBEDDING_API_KEY",
        description="Generic embedding API key override (falls back to VOYAGE_API_KEY or OPENAI_API_KEY).",
    )
    embedding_batch_size: int = Field(
        default=128,
        alias="EMBEDDING_BATCH_SIZE",
        description="Number of texts per embedding batch (VoyageAI supports up to 128).",
    )
    chunk_size: int = Field(default=1000, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=100, alias="CHUNK_OVERLAP")
    indexing_max_retries: int = Field(default=3, alias="INDEXING_MAX_RETRIES")

    # Local folder → Weaviate ingest (``scripts/ingest_local_data.py``)
    local_ingest_company_id: Optional[str] = Field(
        default=None,
        alias="LOCAL_INGEST_COMPANY_ID",
        description="UUID string: load weaviate_collection from DB; also used as company_id on chunks.",
    )
    local_weaviate_collection: Optional[str] = Field(
        default=None,
        alias="LOCAL_WEAVIATE_COLLECTION",
        description="Override Weaviate class name when not resolving from LOCAL_INGEST_COMPANY_ID.",
    )

    # ------------------------------------------------------------------ #
    # Bot / spam protection
    # ------------------------------------------------------------------ #
    bot_protection_enabled: bool = Field(
        default=True,
        alias="BOT_PROTECTION_ENABLED",
        description="Master switch for bot/spam detection on inbound messages.",
    )
    bot_rate_window_seconds: int = Field(
        default=60,
        alias="BOT_RATE_WINDOW_SECONDS",
        description="Look-back window (seconds) for rate-flood detection.",
    )
    bot_max_messages_per_window: int = Field(
        default=10,
        alias="BOT_MAX_MESSAGES_PER_WINDOW",
        description="Max customer messages allowed inside the rate window before blocking.",
    )
    bot_max_identical_messages: int = Field(
        default=4,
        alias="BOT_MAX_IDENTICAL_MESSAGES",
        description="Max times the same message text may appear in the window before blocking.",
    )
    bot_burst_count: int = Field(
        default=5,
        alias="BOT_BURST_COUNT",
        description="Number of consecutive messages inspected for ultra-fast burst detection.",
    )
    bot_burst_interval_seconds: float = Field(
        default=2.0,
        alias="BOT_BURST_INTERVAL_SECONDS",
        description=(
            "Max seconds between consecutive messages to count as a burst. "
            "If all gaps in the last BOT_BURST_COUNT messages are below this, the sender is blocked."
        ),
    )

    # ------------------------------------------------------------------ #
    # Security
    # ------------------------------------------------------------------ #
    secret_key: str = Field(
        default="change-this-in-production", alias="SECRET_KEY"
    )

    # ------------------------------------------------------------------ #
    # Portal API (company-scoped RAG chat + admin)
    # ------------------------------------------------------------------ #
    portal_company_keys_json: Optional[str] = Field(
        default=None,
        alias="PORTAL_COMPANY_KEYS_JSON",
        description=(
            'JSON map of company_id (UUID string) → portal secret, e.g. '
            '{"550e8400-e29b-41d4-a716-446655440000":"tenant-secret-1"}'
        ),
    )
    portal_admin_api_key: Optional[str] = Field(
        default=None,
        alias="PORTAL_ADMIN_API_KEY",
        description=(
            "If set, required as X-Admin-Key for onboarding and company list APIs"
        ),
    )
    portal_bootstrap_secret: Optional[str] = Field(
        default=None,
        alias="PORTAL_BOOTSTRAP_SECRET",
        description=(
            "One-time: create first portal admin via POST .../portal/auth/bootstrap-first-admin "
            "when no portal_users rows exist. Leave unset to disable bootstrap."
        ),
    )
    portal_token_max_age_seconds: int = Field(
        default=86400,
        alias="PORTAL_TOKEN_MAX_AGE_SECONDS",
        description="Max age for Bearer portal tokens (seconds).",
    )

    supabase_jwt_secret: Optional[str] = Field(
        default=None,
        alias="SUPABASE_JWT_SECRET",
        description=(
            "Supabase JWT secret (Project Settings → API). When set, Bearer tokens "
            "are validated as Supabase access JWTs with app_metadata.role "
            "admin | user and optional company_id."
        ),
    )
    cors_origins: str = Field(
        default="",
        alias="CORS_ORIGINS",
        description=(
            "Comma-separated browser origins allowed for CORS. "
            "Empty in development defaults to localhost Vite URLs. "
            "Set to * or use CORS_ALLOW_ALL to allow any origin (credentials disabled)."
        ),
    )
    cors_allow_all: bool = Field(
        default=False,
        alias="CORS_ALLOW_ALL",
        description=(
            "If true, Access-Control-Allow-Origin: * (any origin). "
            "allow_credentials is forced false (browser requirement)."
        ),
    )

    # ------------------------------------------------------------------ #
    # WhatsApp auto-reply control
    # ------------------------------------------------------------------ #
    whatsapp_agent_inactivity_minutes: int = Field(
        default=3,
        alias="WHATSAPP_AGENT_INACTIVITY_MINUTES",
        description=(
            "If you (the human) send messages from the connected WhatsApp number, "
            "the conversation switches to agent mode and the bot pauses. After this "
            "many minutes without any further agent messages, the bot resumes."
        ),
    )

    # ------------------------------------------------------------------ #
    # Computed helpers
    # ------------------------------------------------------------------ #
    @property
    def is_production(self) -> bool:
        """True when running in production environment."""
        return self.app_env.lower() == "production"

    @property
    def is_testing(self) -> bool:
        """True when running under pytest."""
        return self.app_env.lower() == "testing"

    @property
    def uses_sqlite(self) -> bool:
        """True when the configured DB is SQLite (local/test)."""
        return "sqlite" in self.database_url

    @property
    def cors_origins_list(self) -> list[str]:
        """Origins for ``CORSMiddleware`` (empty in production unless CORS_ORIGINS is set)."""
        raw = (self.cors_origins or "").strip()
        if raw:
            return [x.strip() for x in raw.split(",") if x.strip()]
        if not self.is_production:
            return ["http://localhost:5173", "http://127.0.0.1:5173"]
        return []

    @property
    def portal_company_keys(self) -> Dict[str, str]:
        """
        Normalised map ``str(UUID) -> portal secret`` for X-Portal-Company-Key checks.
        """
        if not self.portal_company_keys_json:
            return {}
        raw: Any = json.loads(self.portal_company_keys_json)
        if not isinstance(raw, dict):
            raise ValueError("PORTAL_COMPANY_KEYS_JSON must be a JSON object")
        out: Dict[str, str] = {}
        for k, v in raw.items():
            out[str(UUID(str(k)))] = str(v)
        return out


def get_settings() -> "Settings":
    """Return the singleton settings instance."""
    return _settings


# Module-level singleton — imported everywhere in the codebase.
_settings = Settings()
settings = _settings
