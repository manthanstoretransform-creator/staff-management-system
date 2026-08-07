from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Optional, List
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate

class ProjectRepository:
    @staticmethod
    def get_by_id(db: Session, project_id: int) -> Optional[Project]:
        return db.scalar(select(Project).where(Project.id == project_id))

    @staticmethod
    def list_by_organization(db: Session, organization_id: int) -> List[Project]:
        # Exclude archived from regular list, or return all?
        # Standard behaviour is return all or active ones. We will return all including archived unless told otherwise.
        # But wait, does it matter? It doesn't specify. Let's return all.
        return list(db.scalars(select(Project).where(Project.organization_id == organization_id)).all())

    @staticmethod
    def create(db: Session, project_in: ProjectCreate, organization_id: int, created_by_user_id: int) -> Project:
        db_project = Project(
            organization_id=organization_id,
            project_name=project_in.project_name,
            description=project_in.description,
            start_date=project_in.start_date,
            is_billable=project_in.is_billable,
            created_by=created_by_user_id,
            status="planning"
        )
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        return db_project

    @staticmethod
    def update(db: Session, db_project: Project, project_in: ProjectUpdate) -> Project:
        update_data = project_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_project, field, value)
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        return db_project

    @staticmethod
    def archive(db: Session, db_project: Project) -> Project:
        db_project.status = "archived"
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        return db_project
