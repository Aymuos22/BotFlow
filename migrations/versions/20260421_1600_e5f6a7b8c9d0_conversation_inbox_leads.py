"""Add inbox / lead fields on conversations.

Revision ID: e5f6a7b8c9d0
Revises: c3d4e5f6a7b8
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "lead_warmth",
            sa.String(10),
            nullable=True,
            comment="hot | warm | cold — set on dashboard for sales follow-up",
        ),
    )
    op.add_column(
        "conversations",
        sa.Column(
            "inquiry_complete",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="True when the customer's query is considered complete (manually on dashboard).",
        ),
    )
    op.add_column(
        "conversations",
        sa.Column(
            "inquiry_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When inquiry_complete was set true.",
        ),
    )
    op.create_index(
        "ix_conversations_company_inquiry",
        "conversations",
        ["company_id", "inquiry_complete"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_company_inquiry", table_name="conversations")
    op.drop_column("conversations", "inquiry_completed_at")
    op.drop_column("conversations", "inquiry_complete")
    op.drop_column("conversations", "lead_warmth")
