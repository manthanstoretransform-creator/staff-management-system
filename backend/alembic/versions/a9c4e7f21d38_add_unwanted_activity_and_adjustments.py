"""add_unwanted_activity_and_adjustments

Creates the two tables behind the desktop's unwanted-activity detection:

- time_entry_unwanted_activity: one row per rule-threshold event (e.g.
  "CTRL pressed 15+ times in the rule window") with alert bookkeeping.
- time_entry_adjustments: signed, auditable corrections to reportable
  time. time_entries.total_seconds is never modified; reports add
  SUM(adjustment_seconds) instead.

Also adds client_event_id (idempotency key for the desktop's offline
retry queue) to the pre-existing time_entry_activity table, which gains
its first writer (POST /time-entries/{id}/activity/batch) in the same
change set.

Revision ID: a9c4e7f21d38
Revises: f2b060359157
Create Date: 2026-08-31 20:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a9c4e7f21d38'
down_revision: Union[str, None] = 'f2b060359157'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'time_entry_unwanted_activity' not in tables:
        op.create_table(
            'time_entry_unwanted_activity',
            sa.Column('id', sa.BigInteger(), sa.Identity(always=True), primary_key=True),
            sa.Column('organization_id', sa.BigInteger(), sa.ForeignKey('organizations.id', ondelete='CASCADE', name='fk_unwanted_activity_org'), nullable=False),
            sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE', name='fk_unwanted_activity_user'), nullable=False),
            sa.Column('project_id', sa.BigInteger(), sa.ForeignKey('projects.id', ondelete='CASCADE', name='fk_unwanted_activity_project'), nullable=False),
            sa.Column('task_id', sa.BigInteger(), sa.ForeignKey('tasks.id', ondelete='CASCADE', name='fk_unwanted_activity_task'), nullable=False),
            sa.Column('time_entry_id', sa.BigInteger(), sa.ForeignKey('time_entries.id', ondelete='CASCADE', name='fk_unwanted_activity_entry'), nullable=False),
            sa.Column('activity_type', sa.String(length=50), nullable=False),
            sa.Column('key_or_action', sa.String(length=100), nullable=False),
            sa.Column('occurrence_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('alerted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('alert_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('recorded_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('client_event_id', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        )
        op.create_index('ix_unwanted_activity_time_entry_id', 'time_entry_unwanted_activity', ['time_entry_id'])
        op.create_index('ix_unwanted_activity_organization_id', 'time_entry_unwanted_activity', ['organization_id'])
        op.create_index('ix_unwanted_activity_recorded_at', 'time_entry_unwanted_activity', ['recorded_at'])
        op.create_index(
            'uq_unwanted_activity_client_event_id', 'time_entry_unwanted_activity',
            ['client_event_id'], unique=True, postgresql_where=sa.text('client_event_id IS NOT NULL'),
        )

    if 'time_entry_adjustments' not in tables:
        op.create_table(
            'time_entry_adjustments',
            sa.Column('id', sa.BigInteger(), sa.Identity(always=True), primary_key=True),
            sa.Column('organization_id', sa.BigInteger(), sa.ForeignKey('organizations.id', ondelete='CASCADE', name='fk_time_entry_adjustments_org'), nullable=False),
            sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE', name='fk_time_entry_adjustments_user'), nullable=False),
            sa.Column('project_id', sa.BigInteger(), sa.ForeignKey('projects.id', ondelete='CASCADE', name='fk_time_entry_adjustments_project'), nullable=False),
            sa.Column('task_id', sa.BigInteger(), sa.ForeignKey('tasks.id', ondelete='CASCADE', name='fk_time_entry_adjustments_task'), nullable=False),
            sa.Column('time_entry_id', sa.BigInteger(), sa.ForeignKey('time_entries.id', ondelete='CASCADE', name='fk_time_entry_adjustments_entry'), nullable=False),
            sa.Column('adjustment_seconds', sa.Integer(), nullable=False),
            sa.Column('reason', sa.Text(), nullable=False),
            sa.Column('source_activity_type', sa.String(length=50), nullable=True),
            sa.Column('source_key_or_action', sa.String(length=100), nullable=True),
            sa.Column('unwanted_activity_id', sa.BigInteger(), sa.ForeignKey('time_entry_unwanted_activity.id', ondelete='SET NULL', name='fk_time_entry_adjustments_unwanted'), nullable=True),
            sa.Column('recorded_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('client_event_id', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.CheckConstraint('adjustment_seconds <> 0', name='ck_time_entry_adjustments_nonzero'),
        )
        op.create_index('ix_time_entry_adjustments_time_entry_id', 'time_entry_adjustments', ['time_entry_id'])
        op.create_index('ix_time_entry_adjustments_organization_id', 'time_entry_adjustments', ['organization_id'])
        op.create_index('ix_time_entry_adjustments_recorded_at', 'time_entry_adjustments', ['recorded_at'])
        op.create_index(
            'uq_time_entry_adjustments_client_event_id', 'time_entry_adjustments',
            ['client_event_id'], unique=True, postgresql_where=sa.text('client_event_id IS NOT NULL'),
        )

    # time_entry_activity predates this migration (created directly in the
    # database before any writer existed); give it the idempotency column
    # its first writer needs.
    if 'time_entry_activity' in tables:
        columns = [c['name'] for c in inspector.get_columns('time_entry_activity')]
        if 'client_event_id' not in columns:
            op.add_column('time_entry_activity', sa.Column('client_event_id', sa.String(length=255), nullable=True))
            op.create_index(
                'uq_time_entry_activity_client_event_id', 'time_entry_activity',
                ['client_event_id'], unique=True, postgresql_where=sa.text('client_event_id IS NOT NULL'),
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'time_entry_adjustments' in tables:
        op.drop_table('time_entry_adjustments')
    if 'time_entry_unwanted_activity' in tables:
        op.drop_table('time_entry_unwanted_activity')
    if 'time_entry_activity' in tables:
        columns = [c['name'] for c in inspector.get_columns('time_entry_activity')]
        if 'client_event_id' in columns:
            op.drop_index('uq_time_entry_activity_client_event_id', table_name='time_entry_activity')
            op.drop_column('time_entry_activity', 'client_event_id')
