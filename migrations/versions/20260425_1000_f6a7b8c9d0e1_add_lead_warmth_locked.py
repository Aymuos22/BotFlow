"""Add lead_warmth_locked to skip AI overwrite when set from portal.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "lead_warmth_locked",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="True when lead_warmth was set manually in the portal; AI will not overwrite.",
        ),
    )


def downgrade() -> None:
    op.drop_column("conversations", "lead_warmth_locked")
