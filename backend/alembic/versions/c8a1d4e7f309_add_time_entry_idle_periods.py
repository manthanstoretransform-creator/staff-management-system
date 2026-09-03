"""add_time_entry_idle_periods

Creates `time_entry_idle_periods`, the record of every stretch of
keyboard/mouse inactivity detected during a running timer.

The table is additive only -- no existing table is altered and no data is
rewritten. Idle time that must not be counted is removed through the existing
`time_entry_adjustments` table (a negative row), so `time_entries` keeps
exactly what the timer measured and historical data stays valid.

Two partial unique indexes carry real invariants:

- `uq_idle_periods_pending_entry`: at most one unresolved idle period per
  time entry, so two retries of the same threshold report cannot race into
  two pending popups.
- `uq_idle_periods_client_event_id`: idempotency for the desktop's durable
  offline queue.

Revision ID: c8a1d4e7f309
Revises: b2d3f4a5c6e7
Create Date: 2026-09-02 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c8a1d4e7f309'
down_revision: Union[str, None] = 'b2d3f4a5c6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'time_entry_idle_periods' in inspector.get_table_names():
        return

    op.create_table(
        'time_entry_idle_periods',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column('organization_id', sa.BigInteger(), sa.ForeignKey('organizations.id', ondelete='CASCADE', name='fk_idle_periods_org'), nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE', name='fk_idle_periods_user'), nullable=False),
        sa.Column('time_entry_id', sa.BigInteger(), sa.ForeignKey('time_entries.id', ondelete='CASCADE', name='fk_idle_periods_entry'), nullable=False),
        sa.Column('original_project_id', sa.BigInteger(), sa.ForeignKey('projects.id', ondelete='CASCADE', name='fk_idle_periods_original_project'), nullable=False),
        sa.Column('original_task_id', sa.BigInteger(), sa.ForeignKey('tasks.id', ondelete='CASCADE', name='fk_idle_periods_original_task'), nullable=False),
        sa.Column('idle_started_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('idle_detected_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('idle_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('keep_idle_time', sa.Boolean(), nullable=True),
        sa.Column('action', sa.String(length=20), nullable=True),
        sa.Column('counted', sa.Boolean(), nullable=True),
        sa.Column('reassigned', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('reassigned_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('reassigned_project_id', sa.BigInteger(), sa.ForeignKey('projects.id', ondelete='SET NULL', name='fk_idle_periods_reassigned_project'), nullable=True),
        sa.Column('reassigned_task_id', sa.BigInteger(), sa.ForeignKey('tasks.id', ondelete='SET NULL', name='fk_idle_periods_reassigned_task'), nullable=True),
        sa.Column('reassigned_time_entry_id', sa.BigInteger(), sa.ForeignKey('time_entries.id', ondelete='SET NULL', name='fk_idle_periods_reassigned_entry'), nullable=True),
        sa.Column('reassigned_seconds', sa.Integer(), nullable=True),
        sa.Column('client_event_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("status IN ('pending', 'resolved')", name='ck_idle_periods_status'),
        sa.CheckConstraint("action IS NULL OR action IN ('stop', 'resume')", name='ck_idle_periods_action'),
        sa.CheckConstraint('idle_detected_at >= idle_started_at', name='ck_idle_periods_detected_after_start'),
        sa.CheckConstraint('resolved_at IS NULL OR resolved_at >= idle_started_at', name='ck_idle_periods_resolved_after_start'),
        sa.CheckConstraint('idle_duration_seconds IS NULL OR idle_duration_seconds >= 0', name='ck_idle_periods_duration_nonneg'),
        sa.CheckConstraint('reassigned_seconds IS NULL OR reassigned_seconds > 0', name='ck_idle_periods_reassigned_seconds_positive'),
        sa.CheckConstraint(
            "status <> 'resolved' OR ("
            "resolved_at IS NOT NULL AND keep_idle_time IS NOT NULL "
            "AND action IS NOT NULL AND counted IS NOT NULL "
            "AND idle_duration_seconds IS NOT NULL)",
            name='ck_idle_periods_resolved_complete',
        ),
        sa.CheckConstraint(
            "reassigned = false OR ("
            "reassigned_at IS NOT NULL AND reassigned_project_id IS NOT NULL "
            "AND reassigned_task_id IS NOT NULL AND reassigned_seconds IS NOT NULL)",
            name='ck_idle_periods_reassigned_complete',
        ),
    )

    op.create_index('ix_idle_periods_time_entry_id', 'time_entry_idle_periods', ['time_entry_id'])
    op.create_index('ix_idle_periods_organization_id', 'time_entry_idle_periods', ['organization_id'])
    op.create_index('ix_idle_periods_user_id', 'time_entry_idle_periods', ['user_id'])
    op.create_index('ix_idle_periods_idle_started_at', 'time_entry_idle_periods', ['idle_started_at'])
    op.create_index(
        'uq_idle_periods_pending_entry', 'time_entry_idle_periods', ['time_entry_id'],
        unique=True, postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        'uq_idle_periods_client_event_id', 'time_entry_idle_periods', ['client_event_id'],
        unique=True, postgresql_where=sa.text('client_event_id IS NOT NULL'),
    )
    op.create_index(
        'uq_idle_periods_reassigned_entry', 'time_entry_idle_periods', ['reassigned_time_entry_id'],
        unique=True, postgresql_where=sa.text('reassigned_time_entry_id IS NOT NULL'),
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'time_entry_idle_periods' in inspector.get_table_names():
        op.drop_table('time_entry_idle_periods')
