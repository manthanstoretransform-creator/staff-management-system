from sqlalchemy.orm import Session
from sqlalchemy import text, select
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta, timezone
import logging
import re
import uuid
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
from app.services.external_auth_service import ExternalAuthService

logger = logging.getLogger("uvicorn.error")


def _provider_block_diagnostics(response: httpx.Response) -> tuple[dict[str, str], str | None]:
    """Return non-sensitive details that identify an upstream WAF block."""
    relevant_headers = (
        "server",
        "cf-ray",
        "x-sucuri-id",
        "x-sucuri-cache",
        "x-pantheon-styx-hostname",
        "x-request-id",
        "x-cache",
    )
    headers = {
        name: value
        for name in relevant_headers
        if (value := response.headers.get(name))
    }
    body = response.text if isinstance(response.text, str) else ""
    title_match = re.search(r"<title[^>]*>\s*(.*?)\s*</title>", body, flags=re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip()[:160] if title_match else None
    return headers, title

class AuthService:
    @staticmethod
    async def login_exchange(db: Session, username: str, password: str) -> TokenPair:
        normalized_username = username.strip()
        
        try:
            wp_user = await ExternalAuthService.authenticate(username, password)
        except HTTPException as he:
            logger.error("AUTH_LOGIN_FAILED: Authentication failed for user %s: %s", normalized_username, he.detail)
            raise he
        except Exception as e:
            logger.error("AUTH_LOGIN_FAILED: Unexpected error during login exchange for %s: %s", normalized_username, str(e))
            raise HTTPException(status_code=500, detail=f"Authentication exchange failed: {str(e)}")

        hubstaff_user_id = wp_user.get("hubstaff_user_id")
        hubstaff_user_id = str(hubstaff_user_id).strip() if hubstaff_user_id is not None else None
        email = str(wp_user.get("email", "")).strip().lower()
        name = str(wp_user.get("name", "")).strip()
        if not email or not name:
            logger.error("AUTH_PROVIDER_INVALID_RESPONSE: Response omitted required identity fields")
            raise HTTPException(status_code=502, detail="Invalid authentication provider response")
        hubstaff_designation = wp_user.get("hubstaff_designation")
        idle_enabled = wp_user.get("idle_enabled", True)
        idle_minutes = wp_user.get("idle_minutes", 5)
        capture_frequency = wp_user.get("capture_frequency", 300)

        permission_schema = wp_user.get("permission_schema") or {}
        if not isinstance(permission_schema, dict):
            logger.error("AUTH_PROVIDER_INVALID_RESPONSE: Response returned an invalid permission schema")
            raise HTTPException(status_code=502, detail="Invalid authentication provider response")
        role_name = permission_schema.get("name")
        if not role_name and isinstance(wp_user.get("roles"), list) and wp_user["roles"]:
            role_name = wp_user["roles"][0]
        wp_capabilities = permission_schema.get("permissions")

        if not role_name or role_name not in ROLE_PERMISSIONS:
            logger.error("Unrecognized or missing external role for email %s", email)
            raise HTTPException(status_code=502, detail="Invalid authentication provider response")

        resolved_permissions = {p: True for p in ROLE_PERMISSIONS[role_name]}

        user = UserRepository.get_by_hubstaff_id(db, hubstaff_user_id) if hubstaff_user_id else None
        email_user = UserRepository.get_by_normalized_email(db, email)

        if user and email_user and user.id != email_user.id:
            db.rollback()
            logger.error("External identity/email conflict for email %s", email)
            raise HTTPException(status_code=409, detail="Authenticated identity conflicts with a local account")
        if user is None:
            user = email_user

        if user:
            logger.info("LOCAL_USER_FOUND: Local user found with id %s", user.id)
            if hubstaff_user_id and user.hubstaff_user_id and user.hubstaff_user_id != hubstaff_user_id:
                logger.error("Email identity conflict for local user %s", user.id)
                raise HTTPException(status_code=409, detail="Authenticated identity conflicts with a local account")
            # Sync identity-provider fields, but preserve local profile fields when
            # the provider does not return them.
            if hubstaff_user_id:
                user.hubstaff_user_id = hubstaff_user_id
            user.email = email
            user.name = name
            if hubstaff_designation:
                user.designation = hubstaff_designation
            user.idle_enabled = idle_enabled
            user.idle_minutes = idle_minutes
            user.capture_frequency = capture_frequency
            user.wp_capabilities = wp_capabilities
            user.role_name = role_name
            user.permissions = resolved_permissions
            user.status = "active"
            user.is_active = True
            try:
                db.commit()
                db.refresh(user)
            except IntegrityError:
                db.rollback()
                logger.error("Local user synchronization conflicted for email %s", email)
                raise HTTPException(status_code=409, detail="Authenticated identity conflicts with a local account")
        else:
            logger.info("LOCAL_USER_CREATED: Local user not found; provisioning started")
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
                username=username_val[:255],
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
            try:
                user = UserRepository.create(db, user_create)
            except IntegrityError:
                db.rollback()
                user = (
                    UserRepository.get_by_hubstaff_id(db, hubstaff_user_id)
                    if hubstaff_user_id else None
                ) or UserRepository.get_by_normalized_email(db, email)
                if not user:
                    logger.exception("Local user provisioning failed")
                    raise HTTPException(status_code=500, detail="Unable to provision authenticated user")
                logger.info("Local user provisioning race resolved to id %s", user.id)

        logger.info("Local authentication identity ready with id %s", user.id)
        # Issue the SMS JWT only after local provisioning succeeds.
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        claims = {
            "user_id": user.id,
            "organization_id": user.organization_id,
            "role_name": user.role_name,
            "permissions": user.permissions,
            "exp": expire
        }
        access_token = create_access_token(claims)
        logger.info("JWT_GENERATED: Local access token generated for user id %s", user.id)

        # Generate refresh token
        refresh_token_plain = generate_refresh_token()
        token_hash = hash_token(refresh_token_plain)
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        db_token = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at
        )
        try:
            db.add(db_token)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to persist authentication session for local user %s", user.id)
            raise HTTPException(status_code=500, detail="Unable to create authentication session")

        logger.info("AUTH_LOGIN_SUCCESS: Authentication completed for local user %s", user.id)
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
