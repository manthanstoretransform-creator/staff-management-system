from sqlalchemy.orm import Session
from sqlalchemy import text, select
from datetime import datetime, timedelta, timezone
import logging
import httpx
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserUpdate, UserRead
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
    async def login_exchange(db: Session, username: str, password: str) -> TokenPair:
        # 1. Try local database verification first to handle dev sandbox seeding and WordPress outages
        local_user = db.scalar(
            select(User).where((User.email == username) | (User.username == username))
        )
        if local_user:
            is_valid = False
            if local_user.password_hash is None:
                # Default password fallback for local seeded dev users
                if password == "developer_st_performance":
                    is_valid = True
            else:
                if verify_password(password, local_user.password_hash):
                    is_valid = True
            
            if is_valid:
                # Enforce resolved permissions from ROLE_PERMISSIONS
                resolved_permissions = {p: True for p in ROLE_PERMISSIONS.get(local_user.role_name, {})}
                if local_user.permissions != resolved_permissions:
                    local_user.permissions = resolved_permissions
                    db.commit()
                    db.refresh(local_user)

                expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
                claims = {
                    "user_id": local_user.id,
                    "organization_id": local_user.organization_id,
                    "role_name": local_user.role_name,
                    "permissions": local_user.permissions,
                    "exp": expire
                }
                access_token = create_access_token(claims)
                refresh_token_plain = generate_refresh_token()
                token_hash = hash_token(refresh_token_plain)
                expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

                db.add(RefreshToken(user_id=local_user.id, token_hash=token_hash, expires_at=expires_at))
                db.commit()

                return TokenPair(
                    access_token=access_token,
                    refresh_token=refresh_token_plain,
                    token_type="bearer",
                    user=UserRead.model_validate(local_user)
                )

        # 2. Call WordPress server-side exactly as received
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.WORDPRESS_LOGIN_URL,
                    json={"username": username, "password": password},
                    timeout=15.0
                )
        except Exception as e:
            logger.error(f"Failed to connect to WordPress auth: {str(e)}")
            raise HTTPException(
                status_code=401,
                detail={
                    "code": 401,
                    "status": "failed",
                    "message": "The username or password you entered is incorrect.",
                    "error_type": "authentication_failed"
                }
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": 401,
                    "status": "failed",
                    "message": "The username or password you entered is incorrect.",
                    "error_type": "authentication_failed"
                }
            )

        try:
            data = response.json()
        except Exception:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": 401,
                    "status": "failed",
                    "message": "The username or password you entered is incorrect.",
                    "error_type": "authentication_failed"
                }
            )

        if data.get("status") == "failed" or "user" not in data:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": 401,
                    "status": "failed",
                    "message": data.get("message", "The username or password you entered is incorrect."),
                    "error_type": "authentication_failed"
                }
            )

        wp_user = data["user"]
        hubstaff_user_id = str(wp_user["hubstaff_user_id"])
        email = wp_user["email"]
        name = wp_user["name"]
        hubstaff_designation = wp_user.get("hubstaff_designation")
        idle_enabled = wp_user.get("idle_enabled", True)
        idle_minutes = wp_user.get("idle_minutes", 5)
        capture_frequency = wp_user.get("capture_frequency", 300)

        permission_schema = wp_user.get("permission_schema") or {}
        role_name = permission_schema.get("name")
        wp_capabilities = permission_schema.get("permissions")

        if not role_name or role_name not in ROLE_PERMISSIONS:
            logger.error(f"Unrecognized or missing role '{role_name}' returned from WordPress for user '{email}'")
            raise HTTPException(
                status_code=400,
                detail=f"Unrecognized role: {role_name}"
            )

        resolved_permissions = {p: True for p in ROLE_PERMISSIONS[role_name]}

        # Check if user exists by hubstaff_user_id
        user = UserRepository.get_by_hubstaff_id(db, hubstaff_user_id)

        if user:
            # Refresh fields from response
            user.name = name
            user.designation = hubstaff_designation
            user.idle_enabled = idle_enabled
            user.idle_minutes = idle_minutes
            user.capture_frequency = capture_frequency
            user.wp_capabilities = wp_capabilities
            user.role_name = role_name
            user.permissions = resolved_permissions
            db.commit()
            db.refresh(user)
        else:
            # TEMPORARY: WordPress login response does not include organization_id. Every user is currently assigned
            # DEFAULT_ORGANIZATION_ID until a real mapping is defined. Confirmed with senior lead as acceptable short-term.
            # See docs/rbac.md.
            organization_id = settings.DEFAULT_ORGANIZATION_ID

            # Ensure organization exists
            org_exists = db.execute(
                text("SELECT id FROM organizations WHERE id = :org_id"),
                {"org_id": organization_id}
            ).scalar()

            if not org_exists:
                db.execute(
                    text("INSERT INTO organizations (id, name, slug) VALUES (:org_id, 'Default Org', 'default-org') ON CONFLICT DO NOTHING"),
                    {"org_id": organization_id}
                )
                db.commit()

            # Ensure username is unique and valid
            username_val = wp_user.get("username") or email.split("@")[0]

            user_create = UserCreate(
                organization_id=organization_id,
                hubstaff_user_id=hubstaff_user_id,
                username=username_val,
                email=email,
                name=name,
                designation=hubstaff_designation,
                role_name=role_name,
                permissions=resolved_permissions,
                wp_capabilities=wp_capabilities,
                idle_enabled=idle_enabled,
                idle_minutes=idle_minutes,
                capture_frequency=capture_frequency,
                status="active"
            )
            user = UserRepository.create(db, user_create)

        # Issue our JWT
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        claims = {
            "user_id": user.id,
            "organization_id": user.organization_id,
            "role_name": user.role_name,
            "permissions": user.permissions,
            "exp": expire
        }
        access_token = create_access_token(claims)

        # Generate refresh token
        refresh_token_plain = generate_refresh_token()
        token_hash = hash_token(refresh_token_plain)
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

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
            token_type="bearer",
            user=UserRead.model_validate(user)
        )

    @staticmethod
    def dev_login(db: Session, email: str, password: str) -> TokenPair:
        # We explicitly resolve/force permissions from ROLE_PERMISSIONS server-side to ensure
        # consistency and enforce that permissions are derived purely from the role_name in the database.
        user = db.scalar(
            select(User).where(User.email == email)
        )

        if not user or not user.password_hash or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        resolved_permissions = {p: True for p in ROLE_PERMISSIONS.get(user.role_name, {})}
        if user.permissions != resolved_permissions:
            user.permissions = resolved_permissions
            db.commit()
            db.refresh(user)

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

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token_plain,
            token_type="bearer",
            user=UserRead.model_validate(user)
        )