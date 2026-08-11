"""add_partial_unique_index_active_timer

Revision ID: 62028495eedf
Revises: 3e18f195e839
Create Date: 2026-08-11 12:36:51.910168

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
# Check if imports is defined in context

# revision identifiers, used by Alembic.
revision: str = '62028495eedf'
down_revision: Union[str, None] = '3e18f195e839'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Auto-heal any duplicate active timers by closing the older ones
    op.execute(
        "UPDATE time_entries "
        "SET end_time = start_time + interval '1 hour', total_seconds = 3600 "
        "WHERE end_time IS NULL AND id NOT IN ("
        "  SELECT DISTINCT ON (user_id) id "
        "  FROM time_entries "
        "  WHERE end_time IS NULL "
        "  ORDER BY user_id, start_time DESC"
        ")"
    )

    op.create_index(
        'uq_active_time_entry',
        'time_entries',
        ['user_id'],
        unique=True,
        postgresql_where=sa.text('end_time IS NULL')
    )


def downgrade() -> None:
    op.drop_index(
        'uq_active_time_entry',
        table_name='time_entries'
    )

