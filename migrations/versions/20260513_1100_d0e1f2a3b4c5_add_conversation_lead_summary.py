"""Add stored lead summary fields to conversations.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-05-13 11:00:00+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "lead_summary",
            sa.Text(),
            nullable=True,
            comment="Stored AI summary of the customer's need for CRM and Google Sheets.",
        ),
    )
    op.add_column(
        "conversations",
        sa.Column(
            "lead_summary_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When lead_summary was last generated from customer messages.",
        ),
    )


def downgrade() -> None:
    op.drop_column("conversations", "lead_summary_updated_at")
    op.drop_column("conversations", "lead_summary")
