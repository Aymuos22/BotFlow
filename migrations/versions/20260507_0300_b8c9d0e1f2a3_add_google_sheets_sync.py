"""Add Google Sheets live sync fields.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-05-07 03:00:00+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "company_configs",
        sa.Column(
            "google_sheets_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Mirror inbox conversations/messages to this company's Google Sheet.",
        ),
    )
    op.add_column(
        "company_configs",
        sa.Column(
            "google_sheet_id",
            sa.String(length=128),
            nullable=True,
            comment="Google spreadsheet id used for live inbox/lead sync.",
        ),
    )
    op.add_column(
        "company_configs",
        sa.Column(
            "google_sheet_url",
            sa.String(length=500),
            nullable=True,
            comment="Human-friendly URL for the Google spreadsheet.",
        ),
    )


def downgrade() -> None:
    op.drop_column("company_configs", "google_sheet_url")
    op.drop_column("company_configs", "google_sheet_id")
    op.drop_column("company_configs", "google_sheets_enabled")
