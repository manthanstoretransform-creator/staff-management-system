"""Desktop release endpoints.

Three audiences, three levels of access, kept apart deliberately:

* **The desktop client** (`/desktop/latest-version`) — authenticated. Asks what
  it should be running and gets back everything it needs to install it.
* **The website** (`/desktop/releases/latest`, `/desktop/releases/download`) —
  unauthenticated, because a person downloading Monitra for the first time has
  no account yet. These only ever expose *published* releases.
* **Release management** (`/desktop/releases` and friends) — gated on
  `manage_desktop_releases`, which only administrators hold. Drafts are visible
  here and nowhere else.

The two endpoints that existed before the release table (`/latest-version` and
`/client-versions`) keep their paths, their methods and their response shapes.
Fields were added to the first; nothing was removed or renamed.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.schemas.desktop_release import (
    DesktopReleaseCreate, DesktopReleaseListResponse, DesktopReleaseRead,
    DesktopReleaseUpdate, FleetVersionsResponse, LatestVersionResponse,
    PublicReleaseIndexResponse, PublicReleaseResponse,
)
from app.services.desktop_release import DesktopReleaseService, parse_client_version

router = APIRouter(prefix="/desktop", tags=["Desktop releases"])

#: Only an administrator may register, amend or publish a release. Gating this
#: is the difference between a release channel and an arbitrary-code-execution
#: channel: whoever can publish a release decides what every installed client
#: downloads and runs.
require_release_manager = require_permission("manage_desktop_releases")


# ── The desktop client's update check ──────────────────────────────────────


@router.get("/latest-version", response_model=LatestVersionResponse)
def get_latest_version(
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
    platform: Optional[str] = Header(default=None, alias="X-Monitra-Platform"),
    architecture: Optional[str] = Header(default=None, alias="X-Monitra-Arch"),
    current_version: Optional[str] = Query(
        default=None,
        max_length=32,
        description=(
            "The version the client is running. Optional: it is normally read "
            "from the Monitra/<version> User-Agent the client already sends, "
            "and this parameter only overrides that."
        ),
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The latest published desktop release, and whether the caller is behind it.

    The desktop client polls this on a slow loop. Two things happen here and
    nothing else: the caller is told what the current release is for the
    machine it is running on, and its own version — read from the
    `Monitra/<version>` User-Agent it already sends — is recorded for fleet
    visibility.

    The platform and architecture headers are what keep a Windows client from
    ever being offered a `.dmg`. A caller that sends neither is answered from
    configuration only, which carries no checksum and therefore cannot drive an
    install — an honest degradation rather than a wrong artifact.

    When the deployment has published nothing and has no configured version,
    every field is null and `update_available` is false. That is deliberate: an
    update prompt pointing at a version nobody published would be worse than no
    prompt at all.
    """
    # The header is the normal source; the query parameter exists so a manual
    # "check for updates" can ask about a specific version, and so this is
    # testable without forging a User-Agent.
    client_version = current_version or parse_client_version(user_agent)
    return DesktopReleaseService.latest_version(
        db, current_user, client_version, platform, architecture
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


# ── The public download ────────────────────────────────────────────────────


@router.get("/releases/latest", response_model=PublicReleaseResponse)
def get_public_latest_release(
    platform: str = Query(
        ...,
        max_length=32,
        description="Platform token: win32, darwin, or a friendly alias.",
    ),
    arch: Optional[str] = Query(
        default=None, max_length=32,
        description="CPU architecture: x86_64 or arm64. Required for macOS.",
    ),
    db: Session = Depends(get_db),
):
    """The newest published artifact for one platform.

    Unauthenticated on purpose — someone installing Monitra for the first time
    has no account. Only published releases are ever visible: a draft is not a
    release, and exposing one here would let anyone download a build nobody has
    approved.
    """
    return DesktopReleaseService.public_latest(db, platform=platform, architecture=arch)


@router.get("/releases/downloads", response_model=PublicReleaseIndexResponse)
def get_public_download_index(db: Session = Depends(get_db)):
    """Every platform's current download, for the website's download page.

    This is what makes the download button always current: the page asks for
    "the latest", not for a versioned filename, so a release published six
    months from now is served without the site being redeployed.
    """
    return DesktopReleaseService.public_index(db)


@router.get("/releases/download", response_class=RedirectResponse)
def download_latest_release(
    platform: str = Query(..., max_length=32),
    arch: Optional[str] = Query(default=None, max_length=32),
    db: Session = Depends(get_db),
):
    """Redirect straight to the newest published artifact for a platform.

    A plain link a download button can point at without any JavaScript. It
    redirects rather than proxying the bytes: the artifact lives in release
    storage, and streaming gigabytes through the API would put the whole
    download path behind this application's availability.

    404 when nothing is published for that platform — an error the caller can
    act on, rather than a redirect to nowhere.
    """
    answer = DesktopReleaseService.public_latest(
        db, platform=platform, architecture=arch
    )
    if not answer.available or not answer.download_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No published Monitra release is available for that platform yet.",
        )
    # 302, not 301: the target changes with every release, and a permanent
    # redirect would be cached by browsers and pin users to one version.
    return RedirectResponse(
        url=answer.download_url, status_code=status.HTTP_302_FOUND
    )


# ── Release management ─────────────────────────────────────────────────────


@router.get(
    "/releases",
    response_model=DesktopReleaseListResponse,
    dependencies=[Depends(require_release_manager)],
)
def list_releases(
    status_filter: Optional[str] = Query(default=None, alias="status", max_length=16),
    platform: Optional[str] = Query(default=None, max_length=32),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Every release, drafts included. Administrators only."""
    try:
        releases = DesktopReleaseService.list_releases(
            db, status=status_filter, platform=platform, limit=limit, offset=offset
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=str(exc))
    return DesktopReleaseListResponse(
        releases=[DesktopReleaseRead.model_validate(r) for r in releases]
    )


@router.post(
    "/releases",
    response_model=DesktopReleaseRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_release_manager)],
)
def create_release(
    payload: DesktopReleaseCreate,
    db: Session = Depends(get_db),
):
    """Register a built artifact. Created as a draft, never published here.

    This is the call the release pipeline makes once a build has passed its own
    checks. CI can prove a build compiles and starts; it cannot decide the
    build is good, so it does not get to publish one.
    """
    try:
        release = DesktopReleaseService.create_release(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return DesktopReleaseRead.model_validate(release)


@router.patch(
    "/releases/{release_id}",
    response_model=DesktopReleaseRead,
    dependencies=[Depends(require_release_manager)],
)
def update_release(
    release_id: int,
    payload: DesktopReleaseUpdate,
    db: Session = Depends(get_db),
):
    """Amend a release's notes, its update policy, or its status."""
    try:
        release = DesktopReleaseService.update_release(db, release_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=str(exc))
    if release is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Release not found.")
    return DesktopReleaseRead.model_validate(release)


@router.post(
    "/releases/{release_id}/publish",
    response_model=DesktopReleaseRead,
    dependencies=[Depends(require_release_manager)],
)
def publish_release(release_id: int, db: Session = Depends(get_db)):
    """Make a draft live. From this moment clients are offered it."""
    from app.models.desktop_release import ReleaseStatus

    release = DesktopReleaseService.set_status(db, release_id, ReleaseStatus.PUBLISHED)
    if release is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Release not found.")
    return DesktopReleaseRead.model_validate(release)


@router.post(
    "/releases/{release_id}/rollback",
    response_model=DesktopReleaseRead,
    dependencies=[Depends(require_release_manager)],
)
def rollback_release(release_id: int, db: Session = Depends(get_db)):
    """Withdraw a bad release.

    The row is kept — deleting it would destroy the rollback inventory and make
    every support report naming this build unresolvable. It simply stops being
    offered, and the previous published version becomes the newest again, which
    is the whole rollback mechanism.
    """
    from app.models.desktop_release import ReleaseStatus

    release = DesktopReleaseService.set_status(db, release_id, ReleaseStatus.ROLLED_BACK)
    if release is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Release not found.")
    return DesktopReleaseRead.model_validate(release)
