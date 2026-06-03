"""add_twilio_fields_to_company_configs

Adds two columns to ``company_configs``:
  - ``whatsapp_provider``      VARCHAR(20) NOT NULL DEFAULT 'waha'
  - ``twilio_whatsapp_number`` VARCHAR(50) NULL

``whatsapp_provider`` selects the active WhatsApp transport for a company.
``twilio_whatsapp_number`` stores the per-company Twilio sender in
``whatsapp:+<E.164>`` format and also serves as the inbound routing key
(maps the Twilio webhook ``To`` field to the correct company).

Revision ID: a1b2c3d4e5f6
Revises: 4cc73d8a6e17
Create Date: 2026-04-08 00:00:00.000000+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "4cc73d8a6e17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "company_configs",
        sa.Column(
            "whatsapp_provider",
            sa.String(20),
            nullable=False,
            server_default="waha",
            comment="Active WhatsApp transport provider: waha | twilio",
        ),
    )
    op.add_column(
        "company_configs",
        sa.Column(
            "twilio_whatsapp_number",
            sa.String(50),
            nullable=True,
            comment=(
                "Per-company Twilio WhatsApp sender in whatsapp:+<E.164> format. "
                "Falls back to global TWILIO_WHATSAPP_NUMBER when null. "
                "Also used for inbound routing: maps the Twilio webhook 'To' field "
                "to this company."
            ),
        ),
    )
    # Index for fast inbound routing lookups (To → company).
    op.create_index(
        "ix_company_configs_twilio_whatsapp_number",
        "company_configs",
        ["twilio_whatsapp_number"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_company_configs_twilio_whatsapp_number",
        table_name="company_configs",
    )
    op.drop_column("company_configs", "twilio_whatsapp_number")
    op.drop_column("company_configs", "whatsapp_provider")
