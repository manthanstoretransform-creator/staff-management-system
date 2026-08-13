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
