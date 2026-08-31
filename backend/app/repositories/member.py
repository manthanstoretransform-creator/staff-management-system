from typing import Optional

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.models.user import User


class MemberRepository:
    @staticmethod
    def get_by_id_and_organization(db: Session, member_id: int, organization_id: int) -> Optional[User]:
        return db.scalar(select(User).where(User.id == member_id, User.organization_id == organization_id))

    @staticmethod
    def organization_name(db: Session, organization_id: int) -> Optional[str]:
        """No ORM model maps 'organizations' -- app/models/user.py only registers a stub
        Table(id) so User's FK can resolve, and adding a second declarative model over
        that same table name would collide with it. Raw SQL here matches the exact
        pattern app/services/auth.py already uses to read this table."""
        row = db.execute(text("SELECT name FROM organizations WHERE id = :org_id"), {"org_id": organization_id}).first()
        return row[0] if row else None

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[User]:
        return db.scalar(select(User).where(User.email == email))

    @staticmethod
    def list_by_organization(db: Session, organization_id: int, search: Optional[str], role: Optional[str], status: Optional[str], page: int, limit: int):
        filters = [User.organization_id == organization_id]
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(or_(User.name.ilike(pattern), User.email.ilike(pattern), User.designation.ilike(pattern)))
        if role:
            filters.append(User.role_name == role)
        if status == "active":
            filters.extend([User.status == "active", User.is_active.is_(True)])
        elif status == "inactive":
            filters.append(or_(User.status == "inactive", User.is_active.is_(False)))

        query = select(User).where(*filters).order_by(User.name.asc(), User.id.asc())
        total = db.scalar(select(func.count(User.id)).where(*filters)) or 0
        items = list(db.scalars(query.offset((page - 1) * limit).limit(limit)).all())
        return items, total

    @staticmethod
    def create(db: Session, organization_id: int, data: dict) -> User:
        member = User(
            organization_id=organization_id,
            username=data["email"],
            email=data["email"],
            name=data["name"],
            designation=data["designation"],
            role_name=data["role"],
            status=data["status"],
            is_active=data["status"] == "active",
            date_of_joining=data["date_of_joining"],
            date_of_birth=data["date_of_birth"],
            capture_frequency=300,
        )
        db.add(member)
        db.commit()
        db.refresh(member)
        return member

    @staticmethod
    def save(db: Session, member: User, data: dict) -> User:
        for field, value in data.items():
            setattr(member, "role_name" if field == "role" else field, value)
        if "status" in data:
            member.is_active = data["status"] == "active"
        db.add(member)
        db.commit()
        db.refresh(member)
        return member