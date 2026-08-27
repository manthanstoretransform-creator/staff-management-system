from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List
from sqlalchemy import select
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User
from app.repositories.project_member import ProjectMemberRepository
from app.repositories.user import UserRepository
from app.services.project import ProjectService

class ProjectMemberService:
    ADMIN_ROLES = {"org_admin", "admin", "super_admin"}
    LEADER_ROLES = {"leader", "project_leader"}

    @staticmethod
    def add_members(db: Session, project_id: int, member_ids: List[int], current_user: User) -> dict:
        """Atomically attach active organization users to a project."""
        project = db.scalar(select(Project).where(
            Project.id == project_id,
            Project.organization_id == current_user.organization_id,
            Project.status != "archived",
        ))
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        role = (current_user.role_name or "").lower()
        is_admin = role in ProjectMemberService.ADMIN_ROLES
        is_owning_leader = role in ProjectMemberService.LEADER_ROLES and project.leader_id == current_user.id
        if not (is_admin or is_owning_leader):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an admin or the assigned project leader can add members",
            )

        # Preserve request order while making duplicate input IDs harmless.
        unique_ids = list(dict.fromkeys(member_ids))
        users = list(db.scalars(select(User).where(
            User.id.in_(unique_ids),
            User.organization_id == current_user.organization_id,
            User.is_active.is_(True),
        )).all())
        found_ids = {user.id for user in users}
        invalid_ids = [member_id for member_id in unique_ids if member_id not in found_ids]
        if invalid_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Active member(s) not found in this organization: {invalid_ids}",
            )

        existing_ids = {
            item.user_id for item in db.scalars(select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id.in_(unique_ids),
            )).all()
        }
        added_ids = [member_id for member_id in unique_ids if member_id not in existing_ids]
        if added_ids:
            try:
                ProjectMemberRepository.add_many(
                    db, project_id, current_user.organization_id, added_ids, current_user.id
                )
                db.commit()
            except Exception:
                db.rollback()
                raise

        return {
            "message": "Members added successfully",
            "project_id": project_id,
            "added_member_ids": added_ids,
            "already_assigned_member_ids": [
                member_id for member_id in unique_ids if member_id in existing_ids
            ],
        }

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
