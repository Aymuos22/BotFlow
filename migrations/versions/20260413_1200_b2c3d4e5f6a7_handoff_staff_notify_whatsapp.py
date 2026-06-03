"""Add handoff_staff_notify_whatsapp to company_configs.

Revision ID: b2c3d4e5f6a7
Revises: f1a2b3c4d5e6
Create Date: 2026-04-13 12:00:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "company_configs",
        sa.Column(
            "handoff_staff_notify_whatsapp",
            sa.String(length=50),
            nullable=True,
            comment=(
                "Optional supervisor WhatsApp (whatsapp:+E.164). "
                "When set, a new handoff triggers an outbound WhatsApp alert."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("company_configs", "handoff_staff_notify_whatsapp")
