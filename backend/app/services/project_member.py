from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List
from app.models.project_member import ProjectMember
from app.models.user import User
from app.repositories.project_member import ProjectMemberRepository
from app.repositories.user import UserRepository
from app.services.project import ProjectService

class ProjectMemberService:
    @staticmethod
    def add_member(db: Session, project_id: int, user_id: int, current_user: User) -> ProjectMember:
        # 1. Verify project exists in org
        project = ProjectService.get_project(db, project_id, current_user)
        
        # 2. Verify target user exists and belongs to the same organization
        target_user = UserRepository.get_by_id(db, user_id)
        if not target_user or target_user.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found in this organization"
            )

        # 3. Check for duplicates (no-op return)
        existing = ProjectMemberRepository.get_by_project_and_user(db, project_id, user_id)
        if existing:
            return existing

        # 4. Add member
        return ProjectMemberRepository.add(
            db=db,
            project_id=project_id,
            organization_id=current_user.organization_id,
            user_id=user_id,
            created_by_user_id=current_user.id
        )

    @staticmethod
    def list_members(db: Session, project_id: int, current_user: User) -> List[ProjectMember]:
        # Verify project exists in org
        ProjectService.get_project(db, project_id, current_user)
        return ProjectMemberRepository.list_by_project(db, project_id)

    @staticmethod
    def remove_member(db: Session, project_id: int, user_id: int, current_user: User) -> bool:
        # Verify project exists in org
        ProjectService.get_project(db, project_id, current_user)
        
        # Verify target user belongs to the same organization
        target_user = UserRepository.get_by_id(db, user_id)
        if not target_user or target_user.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found in this organization"
            )
            
        success = ProjectMemberRepository.remove(db, project_id, user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found in project"
            )
        return True
