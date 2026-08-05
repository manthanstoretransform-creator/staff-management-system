from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Optional
from app.models.user import User
from app.schemas.user import UserCreate

class UserRepository:
    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.scalar(select(User).where(User.id == user_id))

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[User]:
        return db.scalar(select(User).where(User.email == email))

    @staticmethod
    def get_by_hubstaff_id(db: Session, hubstaff_user_id: str) -> Optional[User]:
        return db.scalar(select(User).where(User.hubstaff_user_id == hubstaff_user_id))

    @staticmethod
    def create(db: Session, user_in: UserCreate) -> User:
        db_user = User(
            organization_id=user_in.organization_id,
            hubstaff_user_id=user_in.hubstaff_user_id,
            username=user_in.username,
            email=user_in.email,
            name=user_in.name,
            designation=user_in.designation,
            role_name=user_in.role_name,
            permissions=user_in.permissions,
            idle_enabled=user_in.idle_enabled,
            idle_minutes=user_in.idle_minutes,
            capture_frequency=user_in.capture_frequency,
            status=user_in.status
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
