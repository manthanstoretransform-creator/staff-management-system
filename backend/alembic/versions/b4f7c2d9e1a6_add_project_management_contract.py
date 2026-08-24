"""add frontend project management contract

Revision ID: b4f7c2d9e1a6
Revises: a8d2e9f1c4b7
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b4f7c2d9e1a6"
down_revision: Union[str, None] = "a8d2e9f1c4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_statuses",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False, unique=True),
        sa.Column("color", sa.String(length=7), nullable=False),
    )
    op.create_table(
        "task_statuses",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False, unique=True),
        sa.Column("color", sa.String(length=7), nullable=False),
    )
    op.bulk_insert(
        sa.table("project_statuses", sa.column("id", sa.BigInteger()), sa.column("name", sa.String()), sa.column("color", sa.String())),
        [
            {"id": 1, "name": "Active", "color": "#3B82F6"},
            {"id": 2, "name": "Pending", "color": "#F59E0B"},
            {"id": 3, "name": "To Do", "color": "#CBD5E1"},
            {"id": 4, "name": "Completed", "color": "#10B981"},
        ],
    )
    op.bulk_insert(
        sa.table("task_statuses", sa.column("id", sa.BigInteger()), sa.column("name", sa.String()), sa.column("color", sa.String())),
        [
            {"id": 1, "name": "Todo", "color": "#CBD5E1"},
            {"id": 2, "name": "In Progress", "color": "#F59E0B"},
            {"id": 3, "name": "Completed", "color": "#10B981"},
        ],
    )

    op.add_column("projects", sa.Column("status_id", sa.BigInteger(), nullable=True))
    op.add_column("projects", sa.Column("leader_id", sa.BigInteger(), nullable=True))
    op.add_column("projects", sa.Column("deadline", sa.Date(), nullable=True))
    op.add_column("projects", sa.Column("billing_type", sa.String(length=20), nullable=False, server_default=sa.text("'free'")))
    op.add_column("projects", sa.Column("fixed_hours", sa.Numeric(precision=8, scale=2), nullable=True))
    op.add_column("tasks", sa.Column("status_id", sa.BigInteger(), nullable=True))
    op.add_column("tasks", sa.Column("assignee_id", sa.BigInteger(), nullable=True))

    op.execute(sa.text("""
        UPDATE projects
        SET status_id = CASE status
            WHEN 'active' THEN 1
            WHEN 'completed' THEN 4
            WHEN 'todo' THEN 3
            ELSE 2
        END,
        billing_type = 'free'
        WHERE status_id IS NULL
    """))
    op.execute(sa.text("""
        UPDATE tasks
        SET status_id = CASE status
            WHEN 'in_progress' THEN 2
            WHEN 'completed' THEN 3
            ELSE 1
        END
        WHERE status_id IS NULL
    """))
    op.execute(sa.text("""
        UPDATE tasks t
        SET assignee_id = a.user_id
        FROM (
            SELECT DISTINCT ON (task_id) task_id, user_id
            FROM task_assignees
            ORDER BY task_id, id
        ) a
        WHERE t.id = a.task_id AND t.assignee_id IS NULL
    """))

    op.create_foreign_key("fk_projects_status", "projects", "project_statuses", ["status_id"], ["id"])
    op.create_foreign_key("fk_projects_leader", "projects", "users", ["leader_id"], ["id"])
    op.create_foreign_key("fk_tasks_status", "tasks", "task_statuses", ["status_id"], ["id"])
    op.create_foreign_key("fk_tasks_assignee", "tasks", "users", ["assignee_id"], ["id"])
    op.create_index("idx_projects_org_status_id", "projects", ["organization_id", "status_id"])
    op.create_index("idx_projects_org_leader", "projects", ["organization_id", "leader_id"])
    op.create_index("idx_projects_deadline", "projects", ["deadline"])
    op.create_index("idx_tasks_project_status_id", "tasks", ["project_id", "status_id"])


def downgrade() -> None:
    op.drop_index("idx_tasks_project_status_id", table_name="tasks")
    op.drop_index("idx_projects_deadline", table_name="projects")
    op.drop_index("idx_projects_org_leader", table_name="projects")
    op.drop_index("idx_projects_org_status_id", table_name="projects")
    op.drop_constraint("fk_tasks_assignee", "tasks", type_="foreignkey")
    op.drop_constraint("fk_tasks_status", "tasks", type_="foreignkey")
    op.drop_constraint("fk_projects_leader", "projects", type_="foreignkey")
    op.drop_constraint("fk_projects_status", "projects", type_="foreignkey")
    op.drop_column("tasks", "assignee_id")
    op.drop_column("tasks", "status_id")
    op.drop_column("projects", "fixed_hours")
    op.drop_column("projects", "billing_type")
    op.drop_column("projects", "deadline")
    op.drop_column("projects", "leader_id")
    op.drop_column("projects", "status_id")
    op.drop_table("task_statuses")
    op.drop_table("project_statuses")