"""Schemas for the desktop update check and fleet version visibility."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class LatestVersionResponse(BaseModel):
    """What the desktop client asks for on its periodic update check.

    `latest_version` is null when the deployment has not been told what the
    current release is. That is an honest "unknown", and the client treats it
    as "no update to announce" — it must never be filled in with a guess, or
    every user would be prompted to install a version that does not exist.
    """

    #: The newest published release, or null if this deployment does not know.
    latest_version: Optional[str] = None
    #: Where to download it. Null whenever `latest_version` is null.
    download_url: Optional[str] = None
    #: Optional link to the release notes for that version.
    release_notes_url: Optional[str] = None
    #: True only when a known latest version is strictly newer than the
    #: version the caller reported. The server decides this, not the client,
    #: so the comparison rule lives in exactly one place.
    update_available: bool = False
    #: The version the server understood the caller to be running, echoed back
    #: so a mis-parsed User-Agent is visible instead of silent.
    client_version: Optional[str] = None


class DesktopClientVersionRead(BaseModel):
    """One user's last-seen desktop version."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    app_version: str
    platform: Optional[str] = None
    first_seen_at: datetime
    last_seen_at: datetime


class FleetVersionsResponse(BaseModel):
    """Fleet view: who is on what, and how many clients per version."""

    latest_version: Optional[str] = None
    #: version -> number of users last seen on it.
    counts: dict = Field(default_factory=dict)
    clients: List[DesktopClientVersionRead] = Field(default_factory=list)
