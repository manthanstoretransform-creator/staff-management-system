from sqlalchemy.orm import Session
from sqlalchemy import text, select
from datetime import datetime, timedelta, timezone
import logging
from app.repositories.user import UserRepository
from app.schemas.user import HubstaffLoginPayload, UserCreate, UserUpdate
from app.schemas.token import TokenPair
from app.core.security import create_access_token, generate_refresh_token, hash_token, verify_password
from app.core.config import settings
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.core.permissions import ROLE_PERMISSIONS
from fastapi import HTTPException

logger = logging.getLogger("uvicorn.error")

class AuthService:
    @staticmethod
    def login_exchange(db: Session, payload: HubstaffLoginPayload) -> TokenPair:
        # Check if user exists by hubstaff_user_id
        user = UserRepository.get_by_hubstaff_id(db, payload.hubstaff_user_id)

        if user:
            # Update mutable fields but NEVER overwrite role_name or permissions from client payload
            user_update = UserUpdate(
                name=payload.name,
                designation=payload.hubstaff_designation,
                idle_enabled=payload.idle_enabled,
                idle_minutes=payload.idle_minutes,
                capture_frequency=payload.capture_frequency
            )
            user = UserRepository.update(db, user, user_update)
            # Ensure permissions are server-derived only
            resolved_permissions = {p: True for p in ROLE_PERMISSIONS.get(user.role_name, {})}
            if user.permissions != resolved_permissions:
                user.permissions = resolved_permissions
                db.commit()
                db.refresh(user)
        else:
            # Query the organization
            org_exists = db.execute(
                text("SELECT id FROM organizations WHERE id = :org_id"),
                {"org_id": payload.organization_id}
            ).scalar()

            if not org_exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Organization {payload.organization_id} does not exist"
                )

            org_id = payload.organization_id    

            # Validate the incoming role name is a recognized system role
            incoming_role = payload.permission_schema.name
            if incoming_role not in ROLE_PERMISSIONS:
                logger.warning(
                    f"Anomaly detected: Registration attempt with invalid role '{incoming_role}' for user '{payload.email}'"
                )
                raise HTTPException(
                    status_code=400,
                    detail="Invalid role specified"
                )

            # Resolve permissions strictly server-side
            resolved_permissions = {p: True for p in ROLE_PERMISSIONS[incoming_role]}

            user_create = UserCreate(
                organization_id=org_id,
                hubstaff_user_id=payload.hubstaff_user_id,
                username=payload.username,
                email=payload.email,
                name=payload.name,
                designation=payload.hubstaff_designation,
                role_name=incoming_role,
                permissions=resolved_permissions,
                idle_enabled=payload.idle_enabled,
                idle_minutes=payload.idle_minutes,
                capture_frequency=payload.capture_frequency,
                status="active"
            )
            user = UserRepository.create(db, user_create)

        # Generate JWT access token with explicit exp claim
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        claims = {
            "user_id": user.id,
            "organization_id": user.organization_id,
            "role_name": user.role_name,
            "permissions": user.permissions,
            "exp": expire
        }
        access_token = create_access_token(claims)

        # Generate random refresh token and hash it
        refresh_token_plain = generate_refresh_token()
        token_hash = hash_token(refresh_token_plain)
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        # Store refresh token
        db_token = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at
        )
        db.add(db_token)
        db.commit()

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token_plain,
            token_type="bearer"
        )

    @staticmethod
    def dev_login(db: Session, email: str, password: str) -> TokenPair:
        # Load user from SQLAlchemy ORM
        user = db.scalar(
            select(User).where(User.email == email)
        )

        if not user or not user.password_hash or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Resolve permissions strictly server-side to enforce role alignment in DB
        resolved_permissions = {p: True for p in ROLE_PERMISSIONS.get(user.role_name, {})}
        if user.permissions != resolved_permissions:
            user.permissions = resolved_permissions
            db.commit()
            db.refresh(user)

        # Generate JWT access token with explicit exp claim
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        claims = {
            "user_id": user.id,
            "organization_id": user.organization_id,
            "role_name": user.role_name,
            "permissions": user.permissions,
            "exp": expire
        }
        access_token = create_access_token(claims)
        refresh_token_plain = generate_refresh_token()
        token_hash = hash_token(refresh_token_plain)
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        db.add(RefreshToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
        db.commit()

        return TokenPair(access_token=access_token, refresh_token=refresh_token_plain, token_type="bearer")