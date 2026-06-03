"""Add Google Sheets sync retry jobs.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-05-07 03:30:00+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "google_sheet_sync_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(length=30), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_google_sheet_sync_jobs_company_id", "google_sheet_sync_jobs", ["company_id"])
    op.create_index("ix_google_sheet_sync_jobs_entity_id", "google_sheet_sync_jobs", ["entity_id"])
    op.create_index("ix_google_sheet_sync_jobs_next_attempt_at", "google_sheet_sync_jobs", ["next_attempt_at"])
    op.create_index("ix_google_sheet_sync_jobs_status", "google_sheet_sync_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_google_sheet_sync_jobs_status", table_name="google_sheet_sync_jobs")
    op.drop_index("ix_google_sheet_sync_jobs_next_attempt_at", table_name="google_sheet_sync_jobs")
    op.drop_index("ix_google_sheet_sync_jobs_entity_id", table_name="google_sheet_sync_jobs")
    op.drop_index("ix_google_sheet_sync_jobs_company_id", table_name="google_sheet_sync_jobs")
    op.drop_table("google_sheet_sync_jobs")
