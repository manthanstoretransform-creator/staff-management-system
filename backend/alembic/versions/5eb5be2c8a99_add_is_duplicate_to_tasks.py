"""add is_duplicate to tasks

Revision ID: 5eb5be2c8a99
Revises: 472c3616ebd5
Create Date: 2026-08-25 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '5eb5be2c8a99'
down_revision = '472c3616ebd5'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('tasks', sa.Column('is_duplicate', sa.Boolean(), server_default=sa.text('false'), nullable=False))

def downgrade() -> None:
    op.drop_column('tasks', 'is_duplicate')
