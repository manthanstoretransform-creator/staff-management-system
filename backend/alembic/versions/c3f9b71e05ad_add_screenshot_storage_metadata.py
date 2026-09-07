"""Add Google Drive storage metadata to time_entry_screenshots.

Until now the table recorded only *that* a screenshot existed: an
organization, a time entry, a capture time, a free-text `file_path` and a
monitor number. Nothing in it could locate the image, describe it, or tell a
retried upload from a new capture.

This adds the production fields the desktop's screenshot pipeline needs:

* `google_drive_file_id` / `google_drive_folder_id` — where the bytes actually
  are. The view endpoint streams from the file id; the folder id is kept so a
  misfiled object can be traced back to the Year/Month/User/Date folder it
  landed in.
* `file_name`, `file_size_bytes`, `mime_type`, `width`, `height` — the record
  of what was stored, so a grid can lay out and a support question about a
  suspiciously small file can be answered from the database.
* `upload_status` / `uploaded_at` — the lifecycle, constrained to
  pending/uploaded/failed.
* `client_screenshot_id` — the client-generated idempotency key, with a
  **unique** index. The desktop queues captures offline and retries with
  backoff, so a response lost after the file was already stored would produce a
  duplicate Drive file and a duplicate row on the retry. The uniqueness is what
  makes that impossible rather than merely unlikely.

Every column is nullable or defaulted, so existing rows are valid unchanged and
no production data is rewritten. Indexes are added for the queries the timeline
and grid actually run: by entry, and by organization over a capture-time range.

Revision ID: c3f9b71e05ad
Revises: b6d1c8f2a930
Create Date: 2026-09-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3f9b71e05ad'
down_revision: Union[str, None] = 'b6d1c8f2a930'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('time_entry_screenshots', sa.Column('google_drive_file_id', sa.String(length=255), nullable=True))
    op.add_column('time_entry_screenshots', sa.Column('google_drive_folder_id', sa.String(length=255), nullable=True))
    op.add_column('time_entry_screenshots', sa.Column('file_name', sa.String(length=255), nullable=True))
    op.add_column('time_entry_screenshots', sa.Column('file_size_bytes', sa.BigInteger(), nullable=True))
    op.add_column(
        'time_entry_screenshots',
        sa.Column('mime_type', sa.String(length=100), nullable=False, server_default='image/webp'),
    )
    op.add_column('time_entry_screenshots', sa.Column('width', sa.Integer(), nullable=True))
    op.add_column('time_entry_screenshots', sa.Column('height', sa.Integer(), nullable=True))
    op.add_column(
        'time_entry_screenshots',
        sa.Column('upload_status', sa.String(length=20), nullable=False, server_default='uploaded'),
    )
    op.add_column('time_entry_screenshots', sa.Column('uploaded_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('time_entry_screenshots', sa.Column('client_screenshot_id', sa.String(length=64), nullable=True))

    op.create_check_constraint(
        'time_entry_screenshots_upload_status_check',
        'time_entry_screenshots',
        "upload_status IN ('pending', 'uploaded', 'failed')",
    )

    # Idempotency. Partial, because rows that predate this column carry NULL
    # and several NULLs must remain legal.
    op.create_index(
        'uq_time_entry_screenshots_client_id',
        'time_entry_screenshots',
        ['client_screenshot_id'],
        unique=True,
        postgresql_where=sa.text('client_screenshot_id IS NOT NULL'),
    )
    # The timeline groups an entry's screenshots by capture time.
    op.create_index(
        'ix_time_entry_screenshots_entry_captured_at',
        'time_entry_screenshots',
        ['time_entry_id', 'captured_at'],
    )
    # The grid pages an organization's screenshots over a date range.
    op.create_index(
        'ix_time_entry_screenshots_org_captured_at',
        'time_entry_screenshots',
        ['organization_id', 'captured_at'],
    )
    op.create_index(
        'ix_time_entry_screenshots_upload_status',
        'time_entry_screenshots',
        ['upload_status'],
    )


def downgrade() -> None:
    op.drop_index('ix_time_entry_screenshots_upload_status', table_name='time_entry_screenshots')
    op.drop_index('ix_time_entry_screenshots_org_captured_at', table_name='time_entry_screenshots')
    op.drop_index('ix_time_entry_screenshots_entry_captured_at', table_name='time_entry_screenshots')
    op.drop_index('uq_time_entry_screenshots_client_id', table_name='time_entry_screenshots')
    op.drop_constraint(
        'time_entry_screenshots_upload_status_check',
        'time_entry_screenshots',
        type_='check',
    )
    for column in (
        'client_screenshot_id', 'uploaded_at', 'upload_status', 'height', 'width',
        'mime_type', 'file_size_bytes', 'file_name', 'google_drive_folder_id',
        'google_drive_file_id',
    ):
        op.drop_column('time_entry_screenshots', column)
