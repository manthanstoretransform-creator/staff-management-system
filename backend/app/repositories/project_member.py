from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from typing import Iterable, List, Optional
from app.models.project_member import ProjectMember

class ProjectMemberRepository:
    @staticmethod
    def list_by_project(db: Session, project_id: int) -> List[ProjectMember]:
        return list(db.scalars(select(ProjectMember).where(ProjectMember.project_id == project_id)).all())

    @staticmethod
    def get_by_project_and_user(db: Session, project_id: int, user_id: int) -> Optional[ProjectMember]:
        return db.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id
            )
        )

    @staticmethod
    def add(db: Session, project_id: int, organization_id: int, user_id: int, created_by_user_id: int) -> ProjectMember:
        db_member = ProjectMember(
            project_id=project_id,
            organization_id=organization_id,
            user_id=user_id,
            created_by=created_by_user_id
        )
        db.add(db_member)
        db.commit()
        db.refresh(db_member)
        return db_member

    @staticmethod
    def add_many(
        db: Session,
        project_id: int,
        organization_id: int,
        user_ids: Iterable[int],
        created_by_user_id: int,
    ) -> None:
        db.add_all([
            ProjectMember(
                project_id=project_id,
                organization_id=organization_id,
                user_id=user_id,
                created_by=created_by_user_id,
            )
            for user_id in user_ids
        ])

    @staticmethod
    def remove(db: Session, project_id: int, user_id: int) -> bool:
        result = db.execute(
            delete(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id
            )
        )
        db.commit()
        return result.rowcount > 0
