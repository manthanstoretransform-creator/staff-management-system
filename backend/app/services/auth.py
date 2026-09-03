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

def _normalize_role(value) -> str | None:
    """A provider role name reduced to the form ROLE_PERMISSIONS is keyed on.

    Trimmed and lower-cased, so "HR", " hr " and "hr" are one role. Non-strings
    are rejected rather than coerced -- a role is a name, not whatever `str()`
    makes of an object.
    """
    if isinstance(value, str) and (normalized := value.strip().lower()):
        return normalized
    return None


def _provider_roles(wp_user: dict) -> list[str]:
    """The normalised contents of the provider's `user.roles` array."""
    roles = wp_user.get("roles")
    if not isinstance(roles, list):
        return []
    return [normalized for entry in roles if (normalized := _normalize_role(entry))]


def _resolve_provider_role(wp_user: dict, permission_schema: dict) -> tuple[str | None, str, list[str]]:
    """Decide the Monitra role for a provider identity.

    `user.roles` is the source of truth. When the provider names any role
    there, the account's role is one of those roles or the login fails --
    `permission_schema.name` is never consulted as a second opinion.

    That precedence is the whole point, not a detail. The two fields can
    disagree: an HR account came back as roles: ["hr"] alongside
    permission_schema.name: "employee". Preferring the schema name, or falling
    through to it when the roles array named nothing supported, silently signed
    that user in as an employee -- and because login_exchange writes the
    resolved role back with `user.role_name = role_name`, it also rewrote their
    stored role in the database. The user was demoted by logging in, and each
    later login re-applied it. Granting a role the provider did not give is
    exactly the kind of fabricated data this codebase refuses; a login that
    cannot be resolved honestly must fail loudly instead.

    `permission_schema.name` remains the fallback for responses that carry no
    `roles` array at all, which is how this resolved before and must keep
    working.

    Returns the role (or None), the field it came from, and the candidates that
    were considered, so the caller can log precisely why a login was refused.
    """
    provider_roles = _provider_roles(wp_user)
    if provider_roles:
        return (
            next((role for role in provider_roles if role in ROLE_PERMISSIONS), None),
            "user.roles",
            provider_roles,
        )

    schema_role = _normalize_role(permission_schema.get("name"))
    if schema_role:
        return (
            schema_role if schema_role in ROLE_PERMISSIONS else None,
            "permission_schema.name",
            [schema_role],
        )

    return None, "none", []


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
            missing = [
                field for field, value in (("email", email), ("name", name)) if not value
            ]
            logger.error(
                "AUTH_PROVIDER_INVALID_RESPONSE: Response omitted required identity field(s): %s",
                ", ".join(missing),
            )
            raise HTTPException(status_code=502, detail="Invalid authentication provider response")
        hubstaff_designation = wp_user.get("hubstaff_designation")
        idle_enabled = wp_user.get("idle_enabled", True)
        idle_minutes = wp_user.get("idle_minutes", 5)
        capture_frequency = wp_user.get("capture_frequency", 300)

        permission_schema = wp_user.get("permission_schema") or {}
        if not isinstance(permission_schema, dict):
            logger.error(
                "AUTH_PROVIDER_INVALID_RESPONSE: permission_schema is a %s, not an object",
                type(permission_schema).__name__,
            )
            raise HTTPException(status_code=502, detail="Invalid authentication provider response")
        wp_capabilities = permission_schema.get("permissions")

        role_name, role_source, candidates = _resolve_provider_role(wp_user, permission_schema)

        if not role_name:
            # Name the values that were rejected. Without them the log said only
            # that *a* role was unrecognised, which is not enough to tell an
            # unmapped role apart from a provider that sent none -- and left the
            # only way to diagnose a 502 as reproducing it with the user's own
            # credentials. Role names are not sensitive; tokens and passwords
            # are never logged here.
            if not candidates:
                logger.error(
                    "AUTH_PROVIDER_ROLE_MISSING: Provider returned no role for %s "
                    "(user.roles=%r, permission_schema.name=%r)",
                    email, wp_user.get("roles"), permission_schema.get("name"),
                )
            else:
                logger.error(
                    "AUTH_PROVIDER_ROLE_UNSUPPORTED: Provider role(s) %s from %s for %s match "
                    "no Monitra role; supported roles are %s",
                    candidates, role_source, email, sorted(ROLE_PERMISSIONS),
                )
            raise HTTPException(status_code=502, detail="Invalid authentication provider response")

        logger.info(
            "AUTH_PROVIDER_ROLE_RESOLVED: Provider role(s) %s from %s resolved to role_name %r",
            candidates, role_source, role_name,
        )

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

    @staticmethod
    def _issue_token_pair(db: Session, user: User) -> TokenPair:
        """Mint the local access/refresh pair for an already-authenticated user."""
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        claims = {
            "user_id": user.id,
            "organization_id": user.organization_id,
            "role_name": user.role_name,
            "permissions": user.permissions,
            "exp": expire,
        }
        access_token = create_access_token(claims)

        refresh_token_plain = generate_refresh_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        try:
            db.add(RefreshToken(
                user_id=user.id,
                token_hash=hash_token(refresh_token_plain),
                expires_at=expires_at,
            ))
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to persist authentication session for local user %s", user.id)
            raise HTTPException(status_code=500, detail="Unable to create authentication session")

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token_plain,
            token_type="bearer",
            user=UserRead.model_validate(user),
        )

    @staticmethod
    async def sso_exchange(db: Session, provider_token: str) -> TokenPair:
        """
        Exchange a provider-issued JWT (the ?token=... handoff from the performance
        portal) for a local session, so a user arriving from that portal lands on the
        dashboard without typing credentials again.

        The provider token itself is never accepted as a local credential: it is
        verified with the provider, and the local session is issued only for the
        identity the provider reports behind it.
        """
        profile = await ExternalAuthService.authenticate_token(provider_token)

        email = str(profile.get("email", "")).strip().lower()
        name = (
            str(profile.get("display_name") or "").strip()
            or " ".join(part for part in (
                str(profile.get("first_name") or "").strip(),
                str(profile.get("last_name") or "").strip(),
            ) if part).strip()
            or str(profile.get("username") or "").strip()
        )
        if not email or not name:
            logger.error("AUTH_SSO_INVALID_RESPONSE: Provider profile omitted required identity fields")
            raise HTTPException(status_code=502, detail="Invalid authentication provider response")

        user = UserRepository.get_by_normalized_email(db, email)

        if user is None:
            # The provider profile carries no Hubstaff identity, organisation or
            # permission schema, so a role is only accepted when the provider's own
            # role names one this system already defines. Anything else is refused
            # rather than guessed - a fabricated role would silently grant or deny
            # access the provider never authorised.
            provider_roles = profile.get("roles") if isinstance(profile.get("roles"), list) else []
            role_name = next((str(r) for r in provider_roles if str(r) in ROLE_PERMISSIONS), None)
            if not role_name:
                logger.error(
                    "AUTH_SSO_NO_LOCAL_ACCOUNT: No local user for %s and provider roles %s are not mapped",
                    email,
                    provider_roles,
                )
                raise HTTPException(
                    status_code=403,
                    detail="No Monitra account exists for this user yet. Sign in once with your credentials to set it up.",
                )

            organization_id = settings.DEFAULT_ORGANIZATION_ID
            org_exists = db.execute(
                text("SELECT id FROM organizations WHERE id = :org_id"),
                {"org_id": organization_id},
            ).scalar()
            if not org_exists:
                db.execute(
                    text("INSERT INTO organizations (id, name, slug) VALUES (:org_id, 'Default Org', 'default-org') ON CONFLICT DO NOTHING"),
                    {"org_id": organization_id},
                )
                db.commit()

            username_val = str(profile.get("username") or email.split("@")[0])
            user_create = UserCreate(
                organization_id=organization_id,
                username=username_val[:255],
                email=email,
                name=name,
                role_name=role_name,
                permissions={p: True for p in ROLE_PERMISSIONS[role_name]},
                capture_frequency=300,
                status="active",
            )
            try:
                user = UserRepository.create(db, user_create)
            except IntegrityError:
                db.rollback()
                user = UserRepository.get_by_normalized_email(db, email)
                if not user:
                    logger.exception("AUTH_SSO_PROVISIONING_FAILED: Unable to provision %s", email)
                    raise HTTPException(status_code=500, detail="Unable to provision authenticated user")
            logger.info("AUTH_SSO_USER_PROVISIONED: Local user %s created from provider identity", user.id)

        if not user.is_active or user.status != "active":
            logger.error("AUTH_SSO_INACTIVE_ACCOUNT: Local user %s is not active", user.id)
            raise HTTPException(status_code=403, detail="This account is not active")

        logger.info("AUTH_SSO_SUCCESS: Provider token exchanged for a local session for user %s", user.id)
        return AuthService._issue_token_pair(db, user)
