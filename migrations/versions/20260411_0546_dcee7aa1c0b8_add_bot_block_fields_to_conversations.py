"""add_bot_block_fields_to_conversations

Revision ID: dcee7aa1c0b8
Revises: 047d8b74982d
Create Date: 2026-04-11 05:46:47.323034+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dcee7aa1c0b8'
down_revision: Union[str, None] = '047d8b74982d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'conversations',
        sa.Column(
            'is_blocked',
            sa.Boolean(),
            server_default='false',
            nullable=False,
            comment='True when the sender has been identified as a bot or spammer',
        ),
    )
    op.add_column(
        'conversations',
        sa.Column(
            'block_reason',
            sa.Text(),
            nullable=True,
            comment='Human-readable reason this conversation was blocked',
        ),
    )


def downgrade() -> None:
    op.drop_column('conversations', 'block_reason')
    op.drop_column('conversations', 'is_blocked')
