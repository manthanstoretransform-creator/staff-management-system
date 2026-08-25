"""add pending and todo to projects status check constraint

Revision ID: 472c3616ebd5
Revises: c6e8a1f4d2b9
Create Date: 2026-08-25 10:43:01.989017

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
# Check if imports is defined in context

# revision identifiers, used by Alembic.
revision: str = '472c3616ebd5'
down_revision: Union[str, None] = 'c6e8a1f4d2b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing check constraint
    op.drop_constraint('projects_status_check', 'projects', type_='check')
    
    # Create a new check constraint with pending and todo added
    op.create_check_constraint(
        'projects_status_check',
        'projects',
        "status::text = ANY (ARRAY['planning'::character varying, 'active'::character varying, 'pending'::character varying, 'todo'::character varying, 'completed'::character varying, 'cancelled'::character varying, 'archived'::character varying]::text[])"
    )


def downgrade() -> None:
    # Drop the new check constraint
    op.drop_constraint('projects_status_check', 'projects', type_='check')
    
    # Restore the original check constraint
    op.create_check_constraint(
        'projects_status_check',
        'projects',
        "status::text = ANY (ARRAY['planning'::character varying, 'active'::character varying, 'completed'::character varying, 'cancelled'::character varying, 'archived'::character varying]::text[])"
    )
