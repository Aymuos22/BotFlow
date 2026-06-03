"""add conversation opted_out columns

Revision ID: cc7d9e1f2a3b
Revises: b3c4d5e6f7a8
Create Date: 2026-05-29 11:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "cc7d9e1f2a3b"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "opted_out",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "conversations",
        sa.Column(
            "opted_out_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_conversations_opted_out",
        "conversations",
        ["opted_out"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_opted_out", table_name="conversations")
    op.drop_column("conversations", "opted_out_at")
    op.drop_column("conversations", "opted_out")
