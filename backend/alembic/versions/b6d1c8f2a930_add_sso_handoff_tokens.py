"""add sso handoff tokens

Revision ID: b6d1c8f2a930
Revises: a7c4e91b30df
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b6d1c8f2a930"
down_revision: Union[str, None] = "a7c4e91b30df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sso_handoff_tokens",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sso_handoff_tokens"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_sso_handoff_tokens_user",
            ondelete="CASCADE",
        ),
    )
    # Unique: redemption claims the row by its hash, and that claim is what
    # makes a handoff single-use.
    op.create_index(
        "idx_sso_handoff_tokens_token_hash",
        "sso_handoff_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "idx_sso_handoff_tokens_expires_at",
        "sso_handoff_tokens",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_sso_handoff_tokens_expires_at", table_name="sso_handoff_tokens")
    op.drop_index("idx_sso_handoff_tokens_token_hash", table_name="sso_handoff_tokens")
    op.drop_table("sso_handoff_tokens")
