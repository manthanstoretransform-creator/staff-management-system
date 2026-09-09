"""add desktop_releases

Records one row per downloadable desktop artifact, so the update check can
answer with a platform-correct build and the SHA-256 the client verifies before
it runs anything.

The version is stored twice: as the `major.minor.patch` string that names the
build, and as three integer columns that make ordering correct. A string sort
puts '1.9.0' after '1.10.0', which would offer the fleet a downgrade and call
it an update -- so nothing anywhere orders on the string.

Revision ID: a7c41d9e60b3
Revises: c3f9b71e05ad
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c41d9e60b3"
down_revision: Union[str, None] = "c3f9b71e05ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "desktop_releases",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("version_major", sa.Integer(), nullable=False),
        sa.Column("version_minor", sa.Integer(), nullable=False),
        sa.Column("version_patch", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("architecture", sa.String(length=32), nullable=True),
        sa.Column("download_url", sa.String(length=2048), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("release_notes", sa.Text(), nullable=True),
        sa.Column("release_notes_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "force_update",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("min_supported_version", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_desktop_releases"),
        sa.UniqueConstraint(
            "version", "platform", "architecture",
            name="uq_desktop_releases_version_platform_arch",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'disabled', 'rolled_back')",
            name="ck_desktop_releases_status",
        ),
        sa.CheckConstraint(
            "file_size IS NULL OR file_size > 0",
            name="ck_desktop_releases_file_size",
        ),
    )

    # The lookup is always "newest published build for this platform", so the
    # index carries the sort key as well as the filter.
    op.create_index(
        "ix_desktop_releases_lookup",
        "desktop_releases",
        ["platform", "status", "version_major", "version_minor", "version_patch"],
    )

    # Postgres treats NULLs as distinct in a unique index, so the composite
    # constraint above does not actually stop two "any architecture" rows for
    # the same version and platform. This partial index closes that: the
    # Windows installer is one build for every machine, and two rows claiming
    # to be it would make "the latest Windows download" ambiguous.
    op.create_index(
        "uq_desktop_releases_version_platform_noarch",
        "desktop_releases",
        ["version", "platform"],
        unique=True,
        postgresql_where=sa.text("architecture IS NULL"),
        sqlite_where=sa.text("architecture IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_desktop_releases_version_platform_noarch", table_name="desktop_releases"
    )
    op.drop_index("ix_desktop_releases_lookup", table_name="desktop_releases")
    op.drop_table("desktop_releases")
