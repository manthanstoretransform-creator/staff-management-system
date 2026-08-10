from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.task_assignee import TaskAssigneeCreate, TaskAssigneeRead
from app.services.task_assignee import TaskAssigneeService

router = APIRouter(prefix="/projects", tags=["Task Assignees"])

# TODO: Add permission gate for managing task assignees once confirmed

@router.post("/{project_id}/tasks/{task_id}/assignees", response_model=TaskAssigneeRead)
def add_task_assignee(
    project_id: int,
    task_id: int,
    payload: TaskAssigneeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return TaskAssigneeService.add_assignee(db, project_id, task_id, payload.user_id, current_user)

@router.get("/{project_id}/tasks/{task_id}/assignees", response_model=List[TaskAssigneeRead])
def list_task_assignees(
    project_id: int,
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return TaskAssigneeService.list_assignees(db, project_id, task_id, current_user)

@router.delete("/{project_id}/tasks/{task_id}/assignees/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_task_assignee(
    project_id: int,
    task_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    TaskAssigneeService.remove_assignee(db, project_id, task_id, user_id, current_user)
    return
