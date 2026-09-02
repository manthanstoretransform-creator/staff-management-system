"""Add window_seconds to time_entry_activity.

Each row is one desktop capture window. Until now the row carried only the
window's `activity_percentage`, with no record of how long the window was.
That made an honest duration-weighted aggregate impossible: a 12-second tail
window at 100% counted exactly as much as a full 60-second window at 20%.

`window_seconds` records the measured length of the window so the today's
activity summary can compute

    SUM(activity_percentage * window_seconds) / SUM(window_seconds)

in one query. Existing rows are backfilled with 60, which is the desktop's
`ActivityService.WINDOW_SECONDS` and was the only length the client ever
uploaded before this column existed.

Revision ID: b2d3f4a5c6e7
Revises: a9c4e7f21d38
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2d3f4a5c6e7'
down_revision: Union[str, None] = 'a9c4e7f21d38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'time_entry_activity',
        sa.Column(
            'window_seconds',
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text('60'),
        ),
    )
    op.create_check_constraint(
        'time_entry_activity_window_seconds_check',
        'time_entry_activity',
        'window_seconds > 0 AND window_seconds <= 3600',
    )
    # The today's-activity summary filters on recorded_at within an IST day
    # and joins to time_entries; without this the aggregate degrades to a
    # sequential scan of every window the organisation has ever recorded.
    op.create_index(
        'ix_time_entry_activity_entry_recorded_at',
        'time_entry_activity',
        ['time_entry_id', 'recorded_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_time_entry_activity_entry_recorded_at', table_name='time_entry_activity')
    op.drop_constraint(
        'time_entry_activity_window_seconds_check',
        'time_entry_activity',
        type_='check',
    )
    op.drop_column('time_entry_activity', 'window_seconds')
