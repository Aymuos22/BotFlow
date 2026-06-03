"""add per-company twilio credentials

Revision ID: 047d8b74982d
Revises: a1b2c3d4e5f6
Create Date: 2026-04-10 08:06:34.494228+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "047d8b74982d"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "company_configs",
        sa.Column(
            "twilio_account_sid",
            sa.String(80),
            nullable=True,
            comment=(
                "Optional per-company Twilio Account SID (ACxxxxxxxx…). "
                "When set, outbound sending and signature validation should use this "
                "instead of global TWILIO_ACCOUNT_SID."
            ),
        ),
    )
    op.add_column(
        "company_configs",
        sa.Column(
            "twilio_auth_token_encrypted",
            sa.Text(),
            nullable=True,
            comment=(
                "Encrypted per-company Twilio Auth Token (Fernet). "
                "Plaintext is not stored."
            ),
        ),
    )

    # Ensure each Twilio number routes to exactly one company.
    # (Both Postgres and SQLite allow multiple NULLs in a UNIQUE index.)
    op.drop_index(
        "ix_company_configs_twilio_whatsapp_number",
        table_name="company_configs",
    )
    op.create_index(
        "ux_company_configs_twilio_whatsapp_number",
        "company_configs",
        ["twilio_whatsapp_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ux_company_configs_twilio_whatsapp_number",
        table_name="company_configs",
    )
    op.create_index(
        "ix_company_configs_twilio_whatsapp_number",
        "company_configs",
        ["twilio_whatsapp_number"],
        unique=False,
    )
    op.drop_column("company_configs", "twilio_auth_token_encrypted")
    op.drop_column("company_configs", "twilio_account_sid")
