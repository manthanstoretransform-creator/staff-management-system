"""add session_started_at to refresh_tokens

Records when the sign-in a refresh token descends from happened, so rotating
the token can preserve the original session window instead of extending it.
Existing rows are backfilled from created_at, which is the same instant for
every token issued before rotation existed.

Revision ID: a7c4e91b30df
Revises: f3a9c07b21de
Create Date: 2026-09-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a7c4e91b30df'
down_revision = 'f3a9c07b21de'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'refresh_tokens',
        sa.Column('session_started_at', sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE refresh_tokens SET session_started_at = created_at "
        "WHERE session_started_at IS NULL"
    )
    # Refresh now looks tokens up by hash on every access-token renewal; without
    # this that is a sequential scan of every session ever issued.
    op.create_index(
        'ix_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_refresh_tokens_token_hash', table_name='refresh_tokens')
    op.drop_column('refresh_tokens', 'session_started_at')
