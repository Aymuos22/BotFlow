"""Add product synonyms.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-05-14 10:00:00+00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "synonyms_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
            comment="Search synonyms and alternate names for this product.",
        ),
    )


def downgrade() -> None:
    op.drop_column("products", "synonyms_json")
