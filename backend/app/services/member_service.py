import math

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.member import MemberRepository
from app.schemas.member import MemberCreate, MemberUpdate


class MemberService:
    @staticmethod
    def create(db: Session, current_user: User, payload: MemberCreate):
        if MemberRepository.get_by_email(db, payload.email):
            raise HTTPException(status.HTTP_409_CONFLICT, "A member with this email already exists.")
        try:
            return MemberRepository.create(db, current_user.organization_id, payload.model_dump(mode="python"))
        except IntegrityError:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "A member with this email already exists.")

    @staticmethod
    def list(db: Session, current_user: User, search, role, member_status, page, limit):
        items, total = MemberRepository.list_by_organization(db, current_user.organization_id, search, role, member_status, page, limit)
        return {"items": items, "page": page, "limit": limit, "total": total, "pages": math.ceil(total / limit) if total else 0}

    @staticmethod
    def get(db: Session, current_user: User, member_id: int):
        member = MemberRepository.get_by_id_and_organization(db, member_id, current_user.organization_id)
        if not member:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found.")
        return member

    @staticmethod
    def update(db: Session, current_user: User, member_id: int, payload: MemberUpdate):
        member = MemberService.get(db, current_user, member_id)
        data = payload.model_dump(exclude_unset=True, mode="python")
        if "email" in data:
            existing = MemberRepository.get_by_email(db, data["email"])
            if existing and existing.id != member.id:
                raise HTTPException(status.HTTP_409_CONFLICT, "A member with this email already exists.")
        dates = {"date_of_birth": data.get("date_of_birth", member.date_of_birth), "date_of_joining": data.get("date_of_joining", member.date_of_joining)}
        from datetime import date
        if dates["date_of_birth"] and dates["date_of_birth"] > date.today():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Date of birth cannot be in the future")
        if dates["date_of_joining"] and dates["date_of_joining"] > date.today():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Date of joining cannot be in the future")
        try:
            return MemberRepository.save(db, member, data)
        except IntegrityError:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "A member with this email already exists.")

    @staticmethod
    def delete(db: Session, current_user: User, member_id: int):
        member = MemberService.get(db, current_user, member_id)
        if member.id == current_user.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "Users cannot deactivate their own account")
        return MemberRepository.save(db, member, {"status": "inactive"})