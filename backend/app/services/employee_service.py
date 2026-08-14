from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List
from app.models.user import User
from app.repositories.user import UserRepository

class EmployeeService:
    @staticmethod
    def list_employees(db: Session, current_user: User, limit: int = 100, offset: int = 0) -> List[User]:
        return UserRepository.list_by_organization(db, current_user.organization_id, limit, offset)

    @staticmethod
    def get_employee(db: Session, user_id: int, current_user: User) -> User:
        employee = UserRepository.get_by_id_and_organization(db, user_id, current_user.organization_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )
        return employee

    @staticmethod
    def set_employee_status(db: Session, user_id: int, is_active: bool, current_user: User) -> User:
        # Prevent self-deactivation (if current_user.id == user_id) -> raise 409
        if current_user.id == user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Users cannot deactivate their own account"
            )

        employee = UserRepository.get_by_id_and_organization(db, user_id, current_user.organization_id)
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )

        return UserRepository.update_active_status(db, employee, is_active)

    @staticmethod
    def get_dashboard_stats(db: Session, current_user: User) -> dict:
        from app.models.project import Project
        from app.models.task import Task
        from app.models.time_entry import TimeEntry
        from app.models.manual_time_entry import ManualTimeEntry
        from sqlalchemy import select, func

        org_id = current_user.organization_id

        total_projects = db.scalar(
            select(func.count(Project.id))
            .where(Project.organization_id == org_id)
            .where(Project.status != "archived")
        ) or 0

        total_members = db.scalar(
            select(func.count(User.id))
            .where(User.organization_id == org_id)
            .where(User.is_active == True)
        ) or 0

        total_tasks = db.scalar(
            select(func.count(Task.id))
            .join(Project, Task.project_id == Project.id)
            .where(Project.organization_id == org_id)
            .where(Task.status != "archived")
        ) or 0

        auto_seconds = db.scalar(
            select(func.sum(TimeEntry.total_seconds))
            .join(Project, TimeEntry.project_id == Project.id)
            .where(Project.organization_id == org_id)
        ) or 0

        manual_seconds = db.scalar(
            select(func.sum(ManualTimeEntry.total_seconds))
            .join(Project, ManualTimeEntry.project_id == Project.id)
            .where(Project.organization_id == org_id)
            .where(ManualTimeEntry.approval_status == "approved")
        ) or 0

        total_hours = round((auto_seconds + manual_seconds) / 3600.0, 1)

        return {
            "total_projects": total_projects,
            "total_members": total_members,
            "total_tasks": total_tasks,
            "total_hours_tracked": total_hours
        }
