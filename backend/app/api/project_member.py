from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.project_member import ProjectMemberCreate, ProjectMemberRead
from app.services.project_member import ProjectMemberService

router = APIRouter(prefix="/projects", tags=["Project Members"])

# TODO: Add permission gate for managing project members once confirmed

@router.post("/{project_id}/members", response_model=ProjectMemberRead)
def add_project_member(
    project_id: int,
    payload: ProjectMemberCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return ProjectMemberService.add_member(db, project_id, payload.user_id, current_user)

@router.get("/{project_id}/members", response_model=List[ProjectMemberRead])
def list_project_members(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return ProjectMemberService.list_members(db, project_id, current_user)

@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_member(
    project_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ProjectMemberService.remove_member(db, project_id, user_id, current_user)
    return
