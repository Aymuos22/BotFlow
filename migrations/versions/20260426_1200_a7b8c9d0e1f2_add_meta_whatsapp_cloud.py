"""Add Meta WhatsApp Cloud API fields to company_configs.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-26 12:00:00+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "company_configs",
        sa.Column(
            "meta_phone_number_id",
            sa.String(length=32),
            nullable=True,
            comment=(
                "WhatsApp Business phone_number_id from Meta (Cloud API). "
                "Used to route inbound webhooks."
            ),
        ),
    )
    op.add_column(
        "company_configs",
        sa.Column(
            "meta_graph_access_token_encrypted",
            sa.Text(),
            nullable=True,
            comment="Encrypted long-lived Graph API access token for Cloud API sends.",
        ),
    )
    op.add_column(
        "company_configs",
        sa.Column(
            "meta_app_secret_encrypted",
            sa.Text(),
            nullable=True,
            comment=(
                "Encrypted Meta app secret; when set, POST webhooks verify X-Hub-Signature-256."
            ),
        ),
    )
    op.add_column(
        "company_configs",
        sa.Column(
            "meta_webhook_verify_token_encrypted",
            sa.Text(),
            nullable=True,
            comment="Encrypted verify_token string for Meta webhook GET subscription check.",
        ),
    )
    op.create_index(
        "ux_company_configs_meta_phone_number_id",
        "company_configs",
        ["meta_phone_number_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ux_company_configs_meta_phone_number_id",
        table_name="company_configs",
    )
    op.drop_column("company_configs", "meta_webhook_verify_token_encrypted")
    op.drop_column("company_configs", "meta_app_secret_encrypted")
    op.drop_column("company_configs", "meta_graph_access_token_encrypted")
    op.drop_column("company_configs", "meta_phone_number_id")
