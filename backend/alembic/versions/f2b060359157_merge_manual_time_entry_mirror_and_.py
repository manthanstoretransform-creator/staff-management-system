"""merge manual_time_entry mirror and project_member user fk heads

Revision ID: f2b060359157
Revises: ('e1a2b3c4d5f6', 'e1f2a3b4c5d6')
Create Date: 2026-08-31 11:37:26.884455

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
# Check if imports is defined in context

# revision identifiers, used by Alembic.
revision: str = 'f2b060359157'
down_revision: Union[str, None] = ('e1a2b3c4d5f6', 'e1f2a3b4c5d6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
