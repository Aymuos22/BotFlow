"""Add partial unique index to prevent duplicate active conversations per (company, phone).

Deduplicates any existing duplicates first (keeps the most recently active one),
then creates a partial unique index so future concurrent inserts can't race.

Revision ID: dd8e0f2a3b4c
Revises: cc7d9e1f2a3b
Create Date: 2026-06-02 12:00:00.000000
"""
from alembic import op

revision = "dd8e0f2a3b4c"
down_revision = "cc7d9e1f2a3b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Close all duplicate active conversations, keeping the one with the
    # latest last_message_at (or latest created_at if last_message_at is null).
    op.execute(
        """
        UPDATE conversations
        SET status = 'closed'
        WHERE status = 'active'
          AND id NOT IN (
            SELECT DISTINCT ON (company_id, customer_phone) id
            FROM conversations
            WHERE status = 'active'
            ORDER BY company_id, customer_phone,
                     COALESCE(last_message_at, created_at) DESC
          )
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_conversation_company_phone_active
        ON conversations (company_id, customer_phone)
        WHERE status = 'active'
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS uq_conversation_company_phone_active"
    )
