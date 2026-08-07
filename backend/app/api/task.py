from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.task import TaskCreate, TaskUpdate, TaskRead
from app.services.task import TaskService

router = APIRouter(prefix="/projects", tags=["Tasks"])

@router.post("/{project_id}/tasks", response_model=TaskRead)
def create_task(
    project_id: int,
    task_in: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return TaskService.create_task(db, project_id, task_in, current_user)

@router.get("/{project_id}/tasks", response_model=List[TaskRead])
def list_tasks(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return TaskService.list_tasks(db, project_id, current_user)

@router.get("/{project_id}/tasks/{task_id}", response_model=TaskRead)
def get_task(
    project_id: int,
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return TaskService.get_task(db, project_id, task_id, current_user)

@router.put("/{project_id}/tasks/{task_id}", response_model=TaskRead)
def update_task(
    project_id: int,
    task_id: int,
    task_in: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return TaskService.update_task(db, project_id, task_id, task_in, current_user)

@router.patch("/{project_id}/tasks/{task_id}/archive", response_model=TaskRead)
def archive_task(
    project_id: int,
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return TaskService.archive_task(db, project_id, task_id, current_user)
