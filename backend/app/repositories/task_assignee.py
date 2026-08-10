from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from typing import List, Optional
from app.models.task_assignee import TaskAssignee

class TaskAssigneeRepository:
    @staticmethod
    def list_by_task(db: Session, task_id: int) -> List[TaskAssignee]:
        return list(db.scalars(select(TaskAssignee).where(TaskAssignee.task_id == task_id)).all())

    @staticmethod
    def get_by_task_and_user(db: Session, task_id: int, user_id: int) -> Optional[TaskAssignee]:
        return db.scalar(
            select(TaskAssignee).where(
                TaskAssignee.task_id == task_id,
                TaskAssignee.user_id == user_id
            )
        )

    @staticmethod
    def add(db: Session, task_id: int, user_id: int, assigned_by_user_id: int) -> TaskAssignee:
        db_assignee = TaskAssignee(
            task_id=task_id,
            user_id=user_id,
            assigned_by=assigned_by_user_id
        )
        db.add(db_assignee)
        db.commit()
        db.refresh(db_assignee)
        return db_assignee

    @staticmethod
    def remove(db: Session, task_id: int, user_id: int) -> bool:
        result = db.execute(
            delete(TaskAssignee).where(
                TaskAssignee.task_id == task_id,
                TaskAssignee.user_id == user_id
            )
        )
        db.commit()
        return result.rowcount > 0
