from typing import Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.schemas.desktop_release import FleetVersionsResponse, LatestVersionResponse
from app.services.desktop_release import DesktopReleaseService, parse_client_version

router = APIRouter(prefix="/desktop", tags=["Desktop releases"])


@router.get("/latest-version", response_model=LatestVersionResponse)
def get_latest_version(
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
    platform: Optional[str] = Header(default=None, alias="X-Monitra-Platform"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The latest published desktop release, and whether the caller is behind it.

    The desktop client polls this on a slow loop. Two things happen here and
    nothing else: the caller is told what the current release is, and its own
    version — read from the `Monitra/<version>` User-Agent it already sends —
    is recorded for fleet visibility.

    When the deployment has not been told what the latest release is, every
    field is null and `update_available` is false. That is deliberate: an
    update prompt pointing at a version nobody published would be worse than
    no prompt at all.
    """
    return DesktopReleaseService.latest_version(
        db, current_user, parse_client_version(user_agent), platform
    )


@router.get(
    "/client-versions",
    response_model=FleetVersionsResponse,
    dependencies=[Depends(require_permission("view_employees"))],
)
def get_fleet_client_versions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Which desktop version each user in the organization was last seen on.

    Answers "did everyone move off the bad build?" without asking each person.
    Gated behind the same permission as viewing employees, because it is a
    per-person view of staff machines.
    """
    return DesktopReleaseService.fleet_versions(db, current_user)
