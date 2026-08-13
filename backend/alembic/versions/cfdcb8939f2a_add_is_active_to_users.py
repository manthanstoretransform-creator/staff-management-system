"""add_is_active_to_users

Revision ID: cfdcb8939f2a
Revises: 5004b623bc66
Create Date: 2026-08-13 10:29:38.952430

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
# Check if imports is defined in context

# revision identifiers, used by Alembic.
revision: str = 'cfdcb8939f2a'
down_revision: Union[str, None] = '5004b623bc66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true'))
    )


def downgrade() -> None:
    op.drop_column('users', 'is_active')
