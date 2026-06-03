"""create_base_tables

Initial migration — creates all core tables from scratch.

Revision ID: 000000000000
Revises: (none — this is the root)
Create Date: 2026-04-01 00:00:00.000000+00:00

Tables created
--------------
companies, company_configs, conversations, messages,
documents, document_index_jobs, retrieval_logs, handoffs,
company_channels, whatsapp_sessions, daily_company_metrics,
portal_users, onboarding_status

NOTE: Twilio columns on company_configs are intentionally absent here;
they are added by subsequent migrations:
  - a1b2c3d4e5f6  →  whatsapp_provider, twilio_whatsapp_number
  - 047d8b74982d  →  twilio_account_sid, twilio_auth_token_encrypted
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "000000000000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── companies ────────────────────────────────────────────────────────
    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "name",
            sa.String(200),
            nullable=False,
            comment="Unique machine-readable company identifier",
        ),
        sa.Column(
            "display_name",
            sa.String(200),
            nullable=False,
            comment="Human-readable company name shown in UIs",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
            comment="draft | active | inactive | suspended",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_companies_id"), "companies", ["id"], unique=False)
    op.create_index(op.f("ix_companies_name"), "companies", ["name"], unique=True)
    op.create_index(op.f("ix_companies_status"), "companies", ["status"], unique=False)

    # ── company_configs ──────────────────────────────────────────────────
    # Twilio columns are NOT here — added by later migrations.
    op.create_table(
        "company_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column(
            "weaviate_collection",
            sa.String(300),
            nullable=False,
            comment="Deterministic Weaviate collection name for this company",
        ),
        sa.Column(
            "waha_session_name",
            sa.String(200),
            nullable=False,
            comment="Deterministic WAHA session name for this company",
        ),
        sa.Column(
            "waha_dedicated_instance",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment=(
                "If true, this company uses its own WAHA Core instance. "
                "If false, the shared WAHA instance is used."
            ),
        ),
        sa.Column(
            "waha_base_url_override",
            sa.String(500),
            nullable=True,
            comment="Optional: override WAHA_BASE_URL for this company (dedicated instance).",
        ),
        sa.Column(
            "waha_api_key_override",
            sa.String(500),
            nullable=True,
            comment="Optional: override WAHA_API_KEY for this company (dedicated instance).",
        ),
        sa.Column(
            "default_language",
            sa.String(20),
            nullable=False,
            server_default="english",
            comment="english | hindi | hinglish",
        ),
        sa.Column(
            "supported_languages",
            sa.JSON(),
            nullable=False,
            comment="Subset of [english, hindi, hinglish]",
        ),
        sa.Column(
            "system_prompt",
            sa.Text(),
            nullable=True,
            comment="System-level instruction for the AI agent",
        ),
        sa.Column(
            "rag_config_json",
            sa.JSON(),
            nullable=True,
            comment="RAG retrieval tuning parameters (top_k, score_threshold, etc.)",
        ),
        sa.Column(
            "fallback_config_json",
            sa.JSON(),
            nullable=True,
            comment="Behaviour when the RAG pipeline cannot answer",
        ),
        sa.Column(
            "handoff_config_json",
            sa.JSON(),
            nullable=True,
            comment="Human handoff / escalation configuration",
        ),
        sa.Column(
            "business_hours_json",
            sa.JSON(),
            nullable=True,
            comment="Operating hours per timezone for out-of-hours handling",
        ),
        sa.Column(
            "whatsapp_agent_inactivity_minutes",
            sa.Integer(),
            nullable=True,
            comment=(
                "When agent mode is active, the bot auto-resumes after this "
                "many minutes of no agent messages. Null = use server default."
            ),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id"),
    )
    op.create_index(
        op.f("ix_company_configs_company_id"),
        "company_configs",
        ["company_id"],
        unique=True,
    )

    # ── conversations ────────────────────────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column(
            "customer_phone",
            sa.String(30),
            nullable=False,
            comment="Normalized E.164 phone number of the customer",
        ),
        sa.Column(
            "current_mode",
            sa.String(10),
            nullable=False,
            server_default="bot",
            comment="bot | agent – controls auto-reply behaviour",
        ),
        sa.Column(
            "status",
            sa.String(10),
            nullable=False,
            server_default="active",
            comment="active | closed",
        ),
        sa.Column(
            "detected_language",
            sa.String(20),
            nullable=True,
            comment="english | hindi | hinglish – detected from first message",
        ),
        sa.Column(
            "assigned_agent_id",
            sa.String(200),
            nullable=True,
            comment="Identifier of the human agent (future use)",
        ),
        sa.Column(
            "last_message_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp of the most recent message",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_conversations_id"), "conversations", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_conversations_company_id"),
        "conversations",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversations_customer_phone"),
        "conversations",
        ["customer_phone"],
        unique=False,
    )

    # ── messages ─────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column(
            "sender_type",
            sa.String(10),
            nullable=False,
            comment="customer | bot | agent | system",
        ),
        sa.Column("message_text", sa.Text(), nullable=False, comment="Raw message text"),
        sa.Column(
            "normalized_text",
            sa.Text(),
            nullable=True,
            comment="Normalized/transliterated text for search",
        ),
        sa.Column(
            "language",
            sa.String(20),
            nullable=True,
            comment="Detected language of this message",
        ),
        sa.Column(
            "response_type",
            sa.String(20),
            nullable=True,
            comment="rag | fallback | handoff | manual (for bot/agent messages)",
        ),
        sa.Column(
            "waha_message_id",
            sa.String(200),
            nullable=True,
            comment="External WAHA ID for deduplication",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("waha_message_id"),
    )
    op.create_index(op.f("ix_messages_id"), "messages", ["id"], unique=False)
    op.create_index(
        op.f("ix_messages_conversation_id"),
        "messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_messages_company_id"), "messages", ["company_id"], unique=False
    )
    op.create_index(
        op.f("ix_messages_created_at"), "messages", ["created_at"], unique=False
    )

    # ── documents ────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column(
            "file_name",
            sa.String(500),
            nullable=False,
            comment="Original uploaded filename",
        ),
        sa.Column("s3_bucket", sa.String(200), nullable=False, comment="S3 bucket name"),
        sa.Column(
            "s3_key", sa.String(1000), nullable=False, comment="Full S3 object key"
        ),
        sa.Column(
            "mime_type",
            sa.String(200),
            nullable=False,
            server_default="application/octet-stream",
        ),
        sa.Column(
            "file_size",
            sa.BigInteger(),
            nullable=True,
            comment="File size in bytes",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="uploaded",
            comment="uploaded | indexing | indexed | failed",
        ),
        sa.Column(
            "uploaded_by",
            sa.String(200),
            nullable=True,
            comment="Identifier of who uploaded (email or system label)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_documents_id"), "documents", ["id"], unique=False)
    op.create_index(
        op.f("ix_documents_company_id"), "documents", ["company_id"], unique=False
    )
    op.create_index(
        op.f("ix_documents_status"), "documents", ["status"], unique=False
    )

    # ── document_index_jobs ──────────────────────────────────────────────
    op.create_table(
        "document_index_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="pending | processing | completed | failed",
        ),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_document_index_jobs_id"),
        "document_index_jobs",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_index_jobs_company_id"),
        "document_index_jobs",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_index_jobs_document_id"),
        "document_index_jobs",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_index_jobs_status"),
        "document_index_jobs",
        ["status"],
        unique=False,
    )

    # ── retrieval_logs ───────────────────────────────────────────────────
    op.create_table(
        "retrieval_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=False, comment="Original customer query"),
        sa.Column(
            "normalized_query",
            sa.Text(),
            nullable=True,
            comment="Normalized query sent to Weaviate",
        ),
        sa.Column("detected_language", sa.String(20), nullable=True),
        sa.Column("weaviate_collection", sa.String(300), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False, server_default="5"),
        sa.Column(
            "top_score",
            sa.Float(),
            nullable=True,
            comment="Highest relevance score from Weaviate",
        ),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "raw_result_json",
            sa.JSON(),
            nullable=True,
            comment="Full Weaviate search result for debugging",
        ),
        sa.Column(
            "fallback_triggered",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "handoff_triggered",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_retrieval_logs_company_id"),
        "retrieval_logs",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_retrieval_logs_conversation_id"),
        "retrieval_logs",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_retrieval_logs_created_at"),
        "retrieval_logs",
        ["created_at"],
        unique=False,
    )

    # ── handoffs ─────────────────────────────────────────────────────────
    op.create_table(
        "handoffs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "requested_by",
            sa.String(20),
            nullable=False,
            server_default="system",
            comment="system | customer | agent",
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=True,
            comment="Human-readable reason (keyword detected, low-confidence, etc.)",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="requested",
            comment="requested | assigned | active | resolved | cancelled",
        ),
        sa.Column("assigned_agent_id", sa.String(200), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_handoffs_id"), "handoffs", ["id"], unique=False)
    op.create_index(
        op.f("ix_handoffs_company_id"), "handoffs", ["company_id"], unique=False
    )
    op.create_index(
        op.f("ix_handoffs_conversation_id"),
        "handoffs",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_handoffs_status"), "handoffs", ["status"], unique=False
    )

    # ── company_channels ─────────────────────────────────────────────────
    op.create_table(
        "company_channels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column(
            "channel_type",
            sa.String(50),
            nullable=False,
            server_default="whatsapp",
            comment="whatsapp (only supported type in phase 1)",
        ),
        sa.Column(
            "phone_number",
            sa.String(30),
            nullable=False,
            comment="E.164-formatted phone number, e.g. +911234567890",
        ),
        sa.Column(
            "session_name",
            sa.String(200),
            nullable=False,
            comment="WAHA session name linked to this channel",
        ),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
            comment="At most one primary channel per company per channel_type",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="pending | active | inactive",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_company_channels_company_id"),
        "company_channels",
        ["company_id"],
        unique=False,
    )

    # ── whatsapp_sessions ────────────────────────────────────────────────
    op.create_table(
        "whatsapp_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column(
            "session_name",
            sa.String(200),
            nullable=False,
            unique=True,
            comment="Unique WAHA session identifier, deterministic from company_id",
        ),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="STARTING",
            comment="STARTING | SCAN_QR_CODE | WORKING | STOPPED | FAILED",
        ),
        sa.Column("qr_last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "phone_number",
            sa.String(30),
            nullable=True,
            comment="Populated once the WhatsApp account is connected",
        ),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            nullable=True,
            comment="Raw WAHA session metadata for debugging",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_name"),
    )
    op.create_index(
        op.f("ix_whatsapp_sessions_company_id"),
        "whatsapp_sessions",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_whatsapp_sessions_session_name"),
        "whatsapp_sessions",
        ["session_name"],
        unique=True,
    )

    # ── daily_company_metrics ────────────────────────────────────────────
    op.create_table(
        "daily_company_metrics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column(
            "metric_date",
            sa.Date(),
            nullable=False,
            comment="Calendar date (UTC) this row covers",
        ),
        sa.Column("total_messages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bot_messages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "fallback_messages", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("handoff_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "active_conversations", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "avg_bot_response_ms",
            sa.Float(),
            nullable=True,
            comment="Average milliseconds from customer message to bot reply",
        ),
        sa.Column("english_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hindi_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hinglish_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "metric_date", name="uq_daily_metrics_company_date"
        ),
    )
    op.create_index(
        op.f("ix_daily_company_metrics_company_id"),
        "daily_company_metrics",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_daily_company_metrics_metric_date"),
        "daily_company_metrics",
        ["metric_date"],
        unique=False,
    )

    # ── portal_users ─────────────────────────────────────────────────────
    op.create_table(
        "portal_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(150), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role", sa.String(20), nullable=False, comment="admin | user"
        ),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index(
        op.f("ix_portal_users_username"), "portal_users", ["username"], unique=True
    )
    op.create_index(
        op.f("ix_portal_users_company_id"),
        "portal_users",
        ["company_id"],
        unique=False,
    )

    # ── onboarding_status ────────────────────────────────────────────────
    op.create_table(
        "onboarding_status",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column(
            "config_saved", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "weaviate_ready",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="True once the Weaviate collection has been created",
        ),
        sa.Column(
            "waha_session_created",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="True once the WAHA session has been created",
        ),
        sa.Column(
            "waha_connected",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="True once the QR code has been scanned and WhatsApp is connected",
        ),
        sa.Column(
            "activated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="True once the company has been fully activated",
        ),
        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
            comment="Last error message from any onboarding step",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id"),
    )
    op.create_index(
        op.f("ix_onboarding_status_company_id"),
        "onboarding_status",
        ["company_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("onboarding_status")
    op.drop_table("portal_users")
    op.drop_table("daily_company_metrics")
    op.drop_table("whatsapp_sessions")
    op.drop_table("company_channels")
    op.drop_table("handoffs")
    op.drop_table("retrieval_logs")
    op.drop_table("document_index_jobs")
    op.drop_table("documents")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("company_configs")
    op.drop_table("companies")
