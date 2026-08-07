from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta, timezone
from app.repositories.user import UserRepository
from app.schemas.user import HubstaffLoginPayload, UserCreate, UserUpdate
from app.schemas.token import TokenPair
from app.core.security import create_access_token, generate_refresh_token, hash_token
from app.core.config import settings
from app.models.refresh_token import RefreshToken
from fastapi import HTTPException

class AuthService:
    @staticmethod
    def login_exchange(db: Session, payload: HubstaffLoginPayload) -> TokenPair:
        # Check if user exists by hubstaff_user_id
        user = UserRepository.get_by_hubstaff_id(db, payload.hubstaff_user_id)

        if user:
            # Update mutable fields
            user_update = UserUpdate(
                name=payload.name,
                designation=payload.hubstaff_designation,
                role_name=payload.permission_schema.name,
                permissions=payload.permission_schema.permissions,
                idle_enabled=payload.idle_enabled,
                idle_minutes=payload.idle_minutes,
                capture_frequency=payload.capture_frequency
            )
            user = UserRepository.update(db, user, user_update)
        else:
            # Query the first organization to associate the user with, or create one if none exists
            # Validate the organization exists — don't auto-create silently
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

            user_create = UserCreate(
                organization_id=org_id,
                hubstaff_user_id=payload.hubstaff_user_id,
                username=payload.username,
                email=payload.email,
                name=payload.name,
                designation=payload.hubstaff_designation,
                role_name=payload.permission_schema.name,
                permissions=payload.permission_schema.permissions,
                idle_enabled=payload.idle_enabled,
                idle_minutes=payload.idle_minutes,
                capture_frequency=payload.capture_frequency,
                status="active"
            )
            user = UserRepository.create(db, user_create)

        # Generate JWT access token
        claims = {
            "user_id": user.id,
            "organization_id": user.organization_id,
            "role_name": user.role_name,
            "permissions": user.permissions
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
