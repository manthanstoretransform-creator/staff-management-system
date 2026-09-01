"""add_manual_time_entry_mirror_and_soft_delete

Revision ID: e1a2b3c4d5f6
Revises: d7e8f9a0b1c2
Create Date: 2026-08-28 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e1a2b3c4d5f6'
down_revision: Union[str, None] = 'd7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('manual_time_entries')]

    if 'mirrored_time_entry_id' not in columns:
        # Set once, atomically, the moment a manual entry is approved -- the
        # real time_entries row that now carries its hours. Lets reporting
        # sum time_entries alone for approved manual time without double
        # counting the manual_time_entries row it came from, while older
        # approved-before-this-feature rows (mirrored_time_entry_id IS NULL)
        # still fall back to being counted directly.
        op.add_column(
            'manual_time_entries',
            sa.Column('mirrored_time_entry_id', sa.BigInteger(), sa.ForeignKey('time_entries.id', ondelete='SET NULL'), nullable=True),
        )
        op.create_index('idx_manual_time_mirrored_entry', 'manual_time_entries', ['mirrored_time_entry_id'])

    if 'deleted_at' not in columns:
        # Soft delete: a withdrawn pending request stays in history rather
        # than disappearing, but is excluded from normal listings.
        op.add_column(
            'manual_time_entries',
            sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True),
        )
        op.create_index('idx_manual_time_deleted_at', 'manual_time_entries', ['deleted_at'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('manual_time_entries')]

    if 'deleted_at' in columns:
        op.drop_index('idx_manual_time_deleted_at', table_name='manual_time_entries')
        op.drop_column('manual_time_entries', 'deleted_at')

    if 'mirrored_time_entry_id' in columns:
        op.drop_index('idx_manual_time_mirrored_entry', table_name='manual_time_entries')
        op.drop_column('manual_time_entries', 'mirrored_time_entry_id')
