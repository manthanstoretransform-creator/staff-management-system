from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from app.schemas.user import UserRead

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserRead
    #: The sign-in window this pair belongs to, in UTC. Both are optional so
    #: clients written against the older response shape keep validating; the
    #: desktop uses them as the authoritative session boundary instead of
    #: computing one from its own clock.
    session_created_at: Optional[datetime] = None
    session_expires_at: Optional[datetime] = None


class SsoHandoffResponse(BaseModel):
    """A single-use token the desktop client puts in the web client's URL."""
    token: str
    expires_at: datetime


class RefreshRequest(BaseModel):
    """Exchange a refresh token for a new access token."""
    refresh_token: str = Field(..., min_length=1)


class LogoutRequest(BaseModel):
    """Revoke a refresh token. Absent token is accepted and does nothing."""
    refresh_token: Optional[str] = None
