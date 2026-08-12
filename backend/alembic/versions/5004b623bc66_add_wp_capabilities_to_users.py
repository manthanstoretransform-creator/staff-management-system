"""add_wp_capabilities_to_users

Revision ID: 5004b623bc66
Revises: 62028495eedf
Create Date: 2026-08-12 11:11:35.272884

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
# Check if imports is defined in context

# revision identifiers, used by Alembic.
revision: str = '5004b623bc66'
down_revision: Union[str, None] = '62028495eedf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('wp_capabilities', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('users', 'wp_capabilities')
