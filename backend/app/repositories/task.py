from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Optional, List
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate

class TaskRepository:
    @staticmethod
    def get_by_id(db: Session, task_id: int) -> Optional[Task]:
        return db.scalar(select(Task).where(Task.id == task_id))

    @staticmethod
    def list_by_project(db: Session, project_id: int) -> List[Task]:
        return list(db.scalars(select(Task).where(Task.project_id == project_id)).all())

    @staticmethod
    def create(db: Session, task_in: TaskCreate, organization_id: int, project_id: int, created_by_user_id: int) -> Task:
        db_task = Task(
            organization_id=organization_id,
            project_id=project_id,
            task_name=task_in.task_name,
            description=task_in.description,
            start_date=task_in.start_date,
            due_date=task_in.due_date,
            estimated_hours=task_in.estimated_hours,
            created_by=created_by_user_id,
            is_duplicate=task_in.is_duplicate or False,
            status="todo"
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        return db_task

    @staticmethod
    def update(db: Session, db_task: Task, task_in: TaskUpdate) -> Task:
        update_data = task_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_task, field, value)
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        return db_task

    @staticmethod
    def archive(db: Session, db_task: Task) -> Task:
        db_task.status = "archived"
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        return db_task
