"""Remove WAHA; rename message external id column; drop whatsapp_sessions.

Revision ID: f1a2b3c4d5e6
Revises: dcee7aa1c0b8
Create Date: 2026-04-11 12:00:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "dcee7aa1c0b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("whatsapp_sessions")

    op.drop_column("company_configs", "waha_session_name")
    op.drop_column("company_configs", "waha_dedicated_instance")
    op.drop_column("company_configs", "waha_base_url_override")
    op.drop_column("company_configs", "waha_api_key_override")

    op.drop_column("onboarding_status", "waha_session_created")
    op.drop_column("onboarding_status", "waha_connected")

    op.execute(
        "ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_waha_message_id_key"
    )
    op.execute(
        "ALTER TABLE messages RENAME COLUMN waha_message_id TO external_message_id"
    )
    op.execute(
        "ALTER TABLE messages ADD CONSTRAINT messages_external_message_id_key "
        "UNIQUE (external_message_id)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_external_message_id_key"
    )
    op.execute(
        "ALTER TABLE messages RENAME COLUMN external_message_id TO waha_message_id"
    )
    op.execute(
        "ALTER TABLE messages ADD CONSTRAINT messages_waha_message_id_key "
        "UNIQUE (waha_message_id)"
    )

    op.add_column(
        "onboarding_status",
        sa.Column(
            "waha_connected",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "onboarding_status",
        sa.Column(
            "waha_session_created",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    op.add_column(
        "company_configs",
        sa.Column(
            "waha_api_key_override",
            sa.String(length=500),
            nullable=True,
        ),
    )
    op.add_column(
        "company_configs",
        sa.Column(
            "waha_base_url_override",
            sa.String(length=500),
            nullable=True,
        ),
    )
    op.add_column(
        "company_configs",
        sa.Column(
            "waha_dedicated_instance",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "company_configs",
        sa.Column(
            "waha_session_name",
            sa.String(length=200),
            nullable=False,
            server_default="",
        ),
    )

    op.create_table(
        "whatsapp_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("session_name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("qr_last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("phone_number", sa.String(length=30), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_name"),
    )
