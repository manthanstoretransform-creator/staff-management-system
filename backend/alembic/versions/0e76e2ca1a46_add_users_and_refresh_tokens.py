"""add_users_and_refresh_tokens

Revision ID: 0e76e2ca1a46
Revises: None
Create Date: 2026-08-05 16:19:21.759939

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
# Check if imports is defined in context

# revision identifiers, used by Alembic.
revision: str = '0e76e2ca1a46'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('hubstaff_user_id', sa.String(), nullable=True),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('designation', sa.String(), nullable=True),
        sa.Column('role_name', sa.String(), nullable=False),
        sa.Column('permissions', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('idle_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('idle_minutes', sa.Integer(), nullable=False, server_default=sa.text('5')),
        sa.Column('capture_frequency', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default=sa.text("'active'")),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_users_organization', ondelete='CASCADE'),
        sa.UniqueConstraint('hubstaff_user_id'),
        sa.UniqueConstraint('email')
    )

    # Create refresh_tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('token_hash', sa.String(), nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_refresh_tokens_user', ondelete='CASCADE')
    )


def downgrade() -> None:
    op.drop_table('refresh_tokens')
    op.drop_table('users')
