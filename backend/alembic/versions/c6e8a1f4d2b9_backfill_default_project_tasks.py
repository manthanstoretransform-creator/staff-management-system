"""backfill mandatory default project tasks

Revision ID: c6e8a1f4d2b9
Revises: b4f7c2d9e1a6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c6e8a1f4d2b9"
down_revision: Union[str, None] = "b4f7c2d9e1a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_TASKS = (
    "Project Setup / Understanding",
    "Review Client Update",
    "Send Client Update",
    "Internal Discussion",
)


def upgrade() -> None:
    for task_name in DEFAULT_TASKS:
        op.execute(
            sa.text(
                """
                INSERT INTO tasks (organization_id, project_id, task_name, status, status_id, created_by)
                SELECT p.organization_id, p.id, :task_name, 'todo', ts.id, p.created_by
                FROM projects p
                CROSS JOIN task_statuses ts
                WHERE ts.name = 'Todo'
                  AND p.status <> 'archived'
                  AND NOT EXISTS (
                      SELECT 1 FROM tasks t
                      WHERE t.project_id = p.id AND t.task_name = :task_name
                  )
                """
            ).bindparams(task_name=task_name)
        )


def downgrade() -> None:
    for task_name in DEFAULT_TASKS:
        op.execute(
            sa.text(
                "DELETE FROM tasks WHERE task_name = :task_name AND status_id = (SELECT id FROM task_statuses WHERE name = 'Todo')"
            ).bindparams(task_name=task_name)
        )