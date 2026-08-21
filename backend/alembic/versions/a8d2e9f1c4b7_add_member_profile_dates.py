"""add member profile dates

Revision ID: a8d2e9f1c4b7
Revises: cfdcb8939f2a
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a8d2e9f1c4b7"
down_revision: Union[str, None] = "cfdcb8939f2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("date_of_joining", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.create_index("idx_users_organization_status", "users", ["organization_id", "status"])
    op.create_index("idx_users_organization_role", "users", ["organization_id", "role_name"])


def downgrade() -> None:
    op.drop_index("idx_users_organization_role", table_name="users")
    op.drop_index("idx_users_organization_status", table_name="users")
    op.drop_column("users", "date_of_birth")
    op.drop_column("users", "date_of_joining")