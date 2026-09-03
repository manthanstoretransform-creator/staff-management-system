"""Desktop release policy: what the latest version is, and who is on what.

Two responsibilities, both deliberately small:

1. **Answer the desktop's update check.** The latest published version is
   configuration (`DESKTOP_LATEST_VERSION`), set by the release process once a
   draft release is actually published. It is not derived from the newest git
   tag, because a tag exists before anyone has decided the build is good — and
   because un-publishing a bad release has to stop the in-app prompt from
   recommending it. Un-setting the config value is exactly that switch.

2. **Record which version each user is running**, for fleet visibility. This
   happens on the same authenticated request, so it costs nothing extra.

If `DESKTOP_LATEST_VERSION` is unset, the answer is an honest "unknown": no
version, no download URL, `update_available = False`. Nothing here ever
invents a version or a link.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.repositories.desktop_client_version import DesktopClientVersionRepository
from app.schemas.desktop_release import (
    DesktopClientVersionRead, FleetVersionsResponse, LatestVersionResponse,
)

logger = logging.getLogger(__name__)

#: `Monitra/1.0.1` — the identity `desktop/version.py:user_agent()` builds.
#: Anything else (a browser, curl, the React frontend) is not a desktop client
#: and is not recorded.
#:
#: The whole version component must be `major.minor.patch` and nothing else:
#: `desktop/version.py` guarantees that shape, so `Monitra/1.0.0-rc1` is a
#: client this deployment does not recognise, not a 1.0.0 with a suffix to be
#: quietly discarded.
_USER_AGENT_RE = re.compile(r"^Monitra/(\d+\.\d+\.\d+)(?:\s|$)")

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def parse_client_version(user_agent: Optional[str]) -> Optional[str]:
    """Extract the Monitra version from a User-Agent header, if it is one."""
    if not user_agent:
        return None
    match = _USER_AGENT_RE.match(user_agent.strip())
    return match.group(1) if match else None


def version_tuple(version: Optional[str]) -> Optional[Tuple[int, int, int]]:
    """Parse `major.minor.patch` into a comparable tuple, or None.

    Strict on purpose. The desktop's own `version.py` guarantees this exact
    shape, so anything else is a client we cannot reason about — and comparing
    an unparseable version numerically would be a guess, which is how a fleet
    ends up being told to "update" to something older.
    """
    if not version or not _VERSION_RE.match(version.strip()):
        return None
    return tuple(int(part) for part in version.strip().split("."))  # type: ignore[return-value]


class DesktopReleaseService:

    @staticmethod
    def configured_latest_version() -> Optional[str]:
        """The latest published version, or None if this deployment has none."""
        configured = (settings.DESKTOP_LATEST_VERSION or "").strip()
        if not configured:
            return None
        if version_tuple(configured) is None:
            # Misconfiguration must not be served to clients as if it were a
            # release. Log it and answer "unknown" instead.
            logger.warning(
                "DESKTOP_LATEST_VERSION=%r is not a major.minor.patch version; "
                "reporting no known release", configured,
            )
            return None
        return configured

    @staticmethod
    def is_update_available(client_version: Optional[str], latest: Optional[str]) -> bool:
        """True only when `latest` is strictly newer than `client_version`.

        An unknown or unparseable client version yields False: a client that
        did not identify itself is not evidence that it is out of date, and
        prompting it would be prompting on no information.
        """
        client = version_tuple(client_version)
        newest = version_tuple(latest)
        if client is None or newest is None:
            return False
        return newest > client

    @staticmethod
    def record_client_version(
        db: Session,
        current_user: User,
        client_version: Optional[str],
        platform: Optional[str],
    ) -> None:
        """Store the caller's desktop version for fleet visibility.

        Never raises into the request: version visibility is diagnostics, and
        failing an update check because a diagnostics write failed would be a
        worse outcome than not knowing which build someone is on.
        """
        if not client_version or version_tuple(client_version) is None:
            return
        try:
            DesktopClientVersionRepository.upsert(
                db,
                organization_id=current_user.organization_id,
                user_id=current_user.id,
                app_version=client_version,
                platform=(platform or None),
            )
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("could not record desktop client version for user %s",
                             current_user.id)

    @staticmethod
    def latest_version(
        db: Session,
        current_user: User,
        client_version: Optional[str],
        platform: Optional[str] = None,
    ) -> LatestVersionResponse:
        latest = DesktopReleaseService.configured_latest_version()
        DesktopReleaseService.record_client_version(
            db, current_user, client_version, platform
        )
        available = DesktopReleaseService.is_update_available(client_version, latest)
        return LatestVersionResponse(
            latest_version=latest,
            download_url=(settings.DESKTOP_DOWNLOAD_URL or None) if latest else None,
            release_notes_url=(settings.DESKTOP_RELEASE_NOTES_URL or None) if latest else None,
            update_available=available,
            client_version=client_version,
        )

    @staticmethod
    def fleet_versions(db: Session, current_user: User) -> FleetVersionsResponse:
        rows = DesktopClientVersionRepository.list_for_organization(
            db, current_user.organization_id
        )
        return FleetVersionsResponse(
            latest_version=DesktopReleaseService.configured_latest_version(),
            counts=dict(Counter(row.app_version for row in rows)),
            clients=[DesktopClientVersionRead.model_validate(row) for row in rows],
        )
