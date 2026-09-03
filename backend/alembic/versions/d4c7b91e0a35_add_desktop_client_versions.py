"""add_desktop_client_versions

Creates `desktop_client_versions`, the record of which Monitra desktop version
each user was last seen running. It exists so a release rollout can be
observed rather than guessed at: "did everyone move off the bad build", and
"is anyone still on a version too old to have the current features".

Additive only -- no existing table is altered and no data is rewritten.

One row per user (`user_id` is unique), overwritten in place. This is a
current-state table by design, not a history: the question it answers is
"which version is this person on now", and keeping a trail would collect
materially more about staff machines than is needed to answer it.

Revision ID: d4c7b91e0a35
Revises: c8a1d4e7f309
Create Date: 2026-09-03 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4c7b91e0a35'
down_revision: Union[str, None] = 'c8a1d4e7f309'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'desktop_client_versions' in inspector.get_table_names():
        return

    op.create_table(
        'desktop_client_versions',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            'organization_id', sa.BigInteger(),
            sa.ForeignKey('organizations.id', ondelete='CASCADE',
                          name='fk_desktop_client_versions_org'),
            nullable=False,
        ),
        sa.Column(
            'user_id', sa.BigInteger(),
            sa.ForeignKey('users.id', ondelete='CASCADE',
                          name='fk_desktop_client_versions_user'),
            nullable=False, unique=True,
        ),
        sa.Column('app_version', sa.String(length=32), nullable=False),
        sa.Column('platform', sa.String(length=32), nullable=True),
        sa.Column('first_seen_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('last_seen_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index(
        'ix_desktop_client_versions_organization_id',
        'desktop_client_versions', ['organization_id'],
    )
    op.create_index(
        'ix_desktop_client_versions_app_version',
        'desktop_client_versions', ['app_version'],
    )


def downgrade() -> None:
    op.drop_index('ix_desktop_client_versions_app_version',
                  table_name='desktop_client_versions')
    op.drop_index('ix_desktop_client_versions_organization_id',
                  table_name='desktop_client_versions')
    op.drop_table('desktop_client_versions')
