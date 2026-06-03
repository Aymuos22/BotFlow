"""Add AiSensy WhatsApp fields to company_configs.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-21 14:00:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "company_configs",
        sa.Column(
            "aisensy_whatsapp_number",
            sa.String(length=50),
            nullable=True,
            comment=(
                "AiSensy / WhatsApp Business display number for inbound routing "
                "(same whatsapp:+<E.164> convention as Twilio)."
            ),
        ),
    )
    op.add_column(
        "company_configs",
        sa.Column(
            "aisensy_project_id",
            sa.String(length=120),
            nullable=True,
            comment="AiSensy project id (Project API / dashboard).",
        ),
    )
    op.add_column(
        "company_configs",
        sa.Column(
            "aisensy_api_key_encrypted",
            sa.Text(),
            nullable=True,
            comment="Encrypted AiSensy Project API key (Bearer token).",
        ),
    )
    op.create_index(
        "ux_company_configs_aisensy_whatsapp_number",
        "company_configs",
        ["aisensy_whatsapp_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ux_company_configs_aisensy_whatsapp_number",
        table_name="company_configs",
    )
    op.drop_column("company_configs", "aisensy_api_key_encrypted")
    op.drop_column("company_configs", "aisensy_project_id")
    op.drop_column("company_configs", "aisensy_whatsapp_number")
