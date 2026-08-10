"""add password_hash to users

Revision ID: 3e18f195e839
Revises: 0e76e2ca1a46
Create Date: 2026-08-10 12:50:52.577488

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
# Check if imports is defined in context

# revision identifiers, used by Alembic.
revision: str = '3e18f195e839'
down_revision: Union[str, None] = '0e76e2ca1a46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('password_hash', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'password_hash')