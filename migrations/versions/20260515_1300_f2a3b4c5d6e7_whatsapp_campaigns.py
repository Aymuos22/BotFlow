"""Add WhatsApp campaigns, follow-ups, outbox, and suppressions."""
from alembic import op
import sqlalchemy as sa

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_campaigns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("template_name", sa.String(length=200), nullable=False),
        sa.Column("language_code", sa.String(length=20), nullable=False),
        sa.Column("body_variable_mappings", sa.JSON(), nullable=False),
        sa.Column("header_media_url_mapping", sa.String(length=200), nullable=True),
        sa.Column("total_recipients", sa.Integer(), nullable=False),
        sa.Column("queued_count", sa.Integer(), nullable=False),
        sa.Column("sent_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_whatsapp_campaigns_company_id", "whatsapp_campaigns", ["company_id"])
    op.create_index("ix_whatsapp_campaigns_status", "whatsapp_campaigns", ["status"])

    op.create_table(
        "whatsapp_campaign_recipients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("phone_number", sa.String(length=30), nullable=False),
        sa.Column("raw_phone", sa.String(length=100), nullable=False),
        sa.Column("row_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("outbox_job_id", sa.Uuid(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["whatsapp_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_whatsapp_campaign_recipients_campaign_id", "whatsapp_campaign_recipients", ["campaign_id"])
    op.create_index("ix_whatsapp_campaign_recipients_company_id", "whatsapp_campaign_recipients", ["company_id"])
    op.create_index("ix_whatsapp_campaign_recipients_outbox_job_id", "whatsapp_campaign_recipients", ["outbox_job_id"])
    op.create_index("ix_whatsapp_campaign_recipients_phone_number", "whatsapp_campaign_recipients", ["phone_number"])
    op.create_index("ix_whatsapp_campaign_recipients_status", "whatsapp_campaign_recipients", ["status"])

    op.create_table(
        "whatsapp_followup_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("steps_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_whatsapp_followup_rules_company_id", "whatsapp_followup_rules", ["company_id"])

    op.create_table(
        "whatsapp_outbox_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("to_number", sa.String(length=30), nullable=False),
        sa.Column("template_name", sa.String(length=200), nullable=False),
        sa.Column("language_code", sa.String(length=20), nullable=False),
        sa.Column("body_variables_json", sa.JSON(), nullable=False),
        sa.Column("header_media_url", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("recipient_id", sa.Uuid(), nullable=True),
        sa.Column("followup_rule_id", sa.Uuid(), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("followup_step_index", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.String(length=200), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["whatsapp_campaigns.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["followup_rule_id"], ["whatsapp_followup_rules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["recipient_id"], ["whatsapp_campaign_recipients.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("campaign_id", "company_id", "conversation_id", "followup_rule_id", "kind", "next_attempt_at", "recipient_id", "status", "to_number"):
        op.create_index(f"ix_whatsapp_outbox_jobs_{col}", "whatsapp_outbox_jobs", [col])

    op.create_table(
        "whatsapp_suppressions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("phone_number", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("suppressed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "phone_number", name="uq_whatsapp_suppression_company_phone"),
    )
    op.create_index("ix_whatsapp_suppressions_company_id", "whatsapp_suppressions", ["company_id"])
    op.create_index("ix_whatsapp_suppressions_phone_number", "whatsapp_suppressions", ["phone_number"])


def downgrade() -> None:
    op.drop_index("ix_whatsapp_suppressions_phone_number", table_name="whatsapp_suppressions")
    op.drop_index("ix_whatsapp_suppressions_company_id", table_name="whatsapp_suppressions")
    op.drop_table("whatsapp_suppressions")
    for col in ("to_number", "status", "recipient_id", "next_attempt_at", "kind", "followup_rule_id", "conversation_id", "company_id", "campaign_id"):
        op.drop_index(f"ix_whatsapp_outbox_jobs_{col}", table_name="whatsapp_outbox_jobs")
    op.drop_table("whatsapp_outbox_jobs")
    op.drop_index("ix_whatsapp_followup_rules_company_id", table_name="whatsapp_followup_rules")
    op.drop_table("whatsapp_followup_rules")
    op.drop_index("ix_whatsapp_campaign_recipients_status", table_name="whatsapp_campaign_recipients")
    op.drop_index("ix_whatsapp_campaign_recipients_phone_number", table_name="whatsapp_campaign_recipients")
    op.drop_index("ix_whatsapp_campaign_recipients_outbox_job_id", table_name="whatsapp_campaign_recipients")
    op.drop_index("ix_whatsapp_campaign_recipients_company_id", table_name="whatsapp_campaign_recipients")
    op.drop_index("ix_whatsapp_campaign_recipients_campaign_id", table_name="whatsapp_campaign_recipients")
    op.drop_table("whatsapp_campaign_recipients")
    op.drop_index("ix_whatsapp_campaigns_status", table_name="whatsapp_campaigns")
    op.drop_index("ix_whatsapp_campaigns_company_id", table_name="whatsapp_campaigns")
    op.drop_table("whatsapp_campaigns")
