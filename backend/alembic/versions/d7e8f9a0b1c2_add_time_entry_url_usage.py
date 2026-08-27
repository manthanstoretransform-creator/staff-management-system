"""add_time_entry_url_usage

Revision ID: d7e8f9a0b1c2
Revises: c6e8a1f4d2b9
Create Date: 2026-08-26 19:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd7e8f9a0b1c2'
down_revision: Union[str, None] = 'c6e8a1f4d2b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'time_entry_url_usage' not in tables:
        op.create_table(
            'time_entry_url_usage',
            sa.Column('id', sa.BigInteger(), sa.Identity(always=True), primary_key=True),
            sa.Column('organization_id', sa.BigInteger(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
            sa.Column('time_entry_id', sa.BigInteger(), sa.ForeignKey('time_entries.id', ondelete='CASCADE'), nullable=False),
            sa.Column('browser_name', sa.String(length=100), nullable=False),
            sa.Column('domain', sa.String(length=255), nullable=False),
            sa.Column('url', sa.Text(), nullable=True),
            sa.Column('page_title', sa.Text(), nullable=True),
            sa.Column('duration_seconds', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('recorded_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('client_event_id', sa.String(length=255), nullable=True),
            sa.CheckConstraint('duration_seconds >= 0', name='ck_time_entry_url_usage_duration_seconds')
        )
        op.create_index('ix_time_entry_url_usage_time_entry_id', 'time_entry_url_usage', ['time_entry_id'])
        op.create_index('ix_time_entry_url_usage_organization_id', 'time_entry_url_usage', ['organization_id'])
        op.create_index('ix_time_entry_url_usage_domain', 'time_entry_url_usage', ['domain'])
        op.create_index('ix_time_entry_url_usage_recorded_at', 'time_entry_url_usage', ['recorded_at'])
        op.create_index('uq_time_entry_url_usage_client_event_id', 'time_entry_url_usage', ['client_event_id'], unique=True, postgresql_where=sa.text('client_event_id IS NOT NULL'))
    else:
        # Table exists (e.g. pre-existing Neon table); ensure client_event_id column and unique index exist
        columns = [c['name'] for c in inspector.get_columns('time_entry_url_usage')]
        if 'client_event_id' not in columns:
            op.add_column('time_entry_url_usage', sa.Column('client_event_id', sa.String(length=255), nullable=True))
            op.create_index('uq_time_entry_url_usage_client_event_id', 'time_entry_url_usage', ['client_event_id'], unique=True, postgresql_where=sa.text('client_event_id IS NOT NULL'))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'time_entry_url_usage' in tables:
        op.drop_table('time_entry_url_usage')
