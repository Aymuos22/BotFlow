"""Add meta_waba_id to company_configs.

Revision ID: b3c4d5e6f7a8
Revises: f2a3b4c5d6e7
Create Date: 2026-05-20 15:00:00+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "company_configs",
        sa.Column(
            "meta_waba_id",
            sa.String(length=32),
            nullable=True,
            comment=(
                "WhatsApp Business Account id — used for template list/create API. "
                "Auto-resolved from meta_phone_number_id if not set."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("company_configs", "meta_waba_id")
