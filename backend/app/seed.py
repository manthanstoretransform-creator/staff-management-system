import os
import sys
from dotenv import load_dotenv

# Add backend folder to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.task import Task
from app.models.task_assignee import TaskAssignee
from sqlalchemy import text

def main():
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
    db = SessionLocal()

    try:
        # Check if project already exists to prevent duplication
        proj_alpha_exists = db.execute(text("SELECT id FROM projects WHERE project_name = 'Project Alpha' AND organization_id = 1")).fetchone()
        if proj_alpha_exists:
            print("Development test data already exists.")
            return

        # Create Projects
        proj_alpha = Project(
            organization_id=1,
            project_name="Project Alpha",
            description="Alpha project for testing",
            status="active",
            is_billable=True,
            created_by=54
        )
        db.add(proj_alpha)

        proj_beta = Project(
            organization_id=1,
            project_name="Project Beta",
            description="Beta project for testing",
            status="active",
            is_billable=False,
            created_by=54
        )
        db.add(proj_beta)
        db.commit()
        db.refresh(proj_alpha)
        db.refresh(proj_beta)

        print(f"Created Project Alpha (ID: {proj_alpha.id})")
        print(f"Created Project Beta (ID: {proj_beta.id})")

        # Project Membership
        pm_alpha = ProjectMember(
            organization_id=1,
            project_id=proj_alpha.id,
            user_id=36,
            created_by=54
        )
        db.add(pm_alpha)
        db.commit()
        db.refresh(pm_alpha)

        print(f"Added user 36 to Project Alpha membership (ID: {pm_alpha.id})")

        # Create Test Tasks
        task_timer = Task(
            organization_id=1,
            project_id=proj_alpha.id,
            task_name="Timer Testing Task",
            description="Task to test timer start/stop functionality",
            status="todo",
            created_by=54
        )
        db.add(task_timer)

        task_admin = Task(
            organization_id=1,
            project_id=proj_beta.id,
            task_name="Admin Core Task",
            description="Internal admin-only task",
            status="todo",
            created_by=54
        )
        db.add(task_admin)
        db.commit()
        db.refresh(task_timer)
        db.refresh(task_admin)

        print(f"Created Timer Testing Task (ID: {task_timer.id})")
        print(f"Created Admin Core Task (ID: {task_admin.id})")

        # Assign Task 1 to Employee ID 36
        assign_timer = TaskAssignee(
            task_id=task_timer.id,
            user_id=36,
            assigned_by=54
        )
        db.add(assign_timer)
        db.commit()
        db.refresh(assign_timer)

        print(f"Assigned user 36 to Timer Testing Task (ID: {assign_timer.id})")

    except Exception as e:
        db.rollback()
        print(f"Seeding failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
