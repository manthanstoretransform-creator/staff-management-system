from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.repositories.project import ProjectRepository

class ProjectService:
    @staticmethod
    def create_project(db: Session, project_in: ProjectCreate, current_user: User) -> Project:
        return ProjectRepository.create(
            db=db,
            project_in=project_in,
            organization_id=current_user.organization_id,
            created_by_user_id=current_user.id
        )

    @staticmethod
    def list_projects(db: Session, current_user: User) -> List[Project]:
        return ProjectRepository.list_by_organization(db, current_user.organization_id)

    @staticmethod
    def get_project(db: Session, project_id: int, current_user: User) -> Project:
        project = ProjectRepository.get_by_id(db, project_id)
        if not project or project.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        return project

    @staticmethod
    def update_project(db: Session, project_id: int, project_in: ProjectUpdate, current_user: User) -> Project:
        project = ProjectRepository.get_by_id(db, project_id)
        if not project or project.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        return ProjectRepository.update(db, project, project_in)

    @staticmethod
    def archive_project(db: Session, project_id: int, current_user: User) -> Project:
        project = ProjectRepository.get_by_id(db, project_id)
        if not project or project.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        return ProjectRepository.archive(db, project)
