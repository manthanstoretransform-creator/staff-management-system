"""add feedback requests

Revision ID: f3a9c07b21de
Revises: d4c7b91e0a35
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3a9c07b21de"
down_revision: Union[str, None] = "d4c7b91e0a35"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feedback_requests",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'new'"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_feedback_requests"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_feedback_requests_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_feedback_requests_user",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "idx_feedback_requests_org_status",
        "feedback_requests",
        ["organization_id", "status"],
    )
    op.create_index(
        "idx_feedback_requests_user_created_at",
        "feedback_requests",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_feedback_requests_user_created_at", table_name="feedback_requests")
    op.drop_index("idx_feedback_requests_org_status", table_name="feedback_requests")
    op.drop_table("feedback_requests")
