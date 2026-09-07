"""
update_service — tells the user when a newer Monitra release exists.

This is "Phase 0" of the update story, and its scope is deliberately narrow:
it *announces*, it does not download and it does not install. Anything that
downloads and runs an installer is a materially larger change to a
stability-critical runtime, and it is gated on code signing — an auto-updater
that silently runs an unsigned installer is a worse security posture than the
manual download it replaces.

Design constraints this service is built to, all of them from DO_NOT_DO.md:

**No new mechanism.** It is a `LoopService` like every other periodic service,
registered with `ApplicationRuntime`, and it notifies through the
`NotificationService` that already owns notifications. No new thread, no new
timer, no second notification path.

**Edge-triggered, never level-triggered.** The check runs on a slow loop and
the backend keeps answering "1.1.0 is available" every time. Notifying on each
answer would be exactly the level-triggered signal that once produced a
notification storm, so the announcement fires only when the announced version
*changes* — once per release, per session.

**The backend decides.** Whether an update exists is `update_available` from
the server, not a comparison made here. One comparison rule, in one place.
A deployment that does not know its latest release answers "unknown", and an
unknown is never rendered as an update.

**It holds instead of failing.** Unauthenticated, offline, or a backend that
does not implement the endpoint (an older deployment, which is a normal state
during a rollout) are all reasons to wait quietly, not to raise or to degrade
anything the user can see. A failed update check must never be able to affect
tracking.

**A toast is not the whole feature.** A notification is transient: the user who
is away from the machine, or who dismisses it without reading, has no way back
to it. So every announced version is also recorded durably, and the count of
versions newer than the one actually installed is published as a badge on the
account menu's "Updates" entry. That count is *derived*, never incremented and
decremented: it is the number of recorded versions strictly newer than
`version.VERSION`, so installing the update makes the badge disappear on the
next launch by arithmetic rather than by anyone remembering to clear a flag.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Signal

import version
from app.api.exceptions import ApiError
from app.updates.service import UpdateApiService
from background_services.network import NetworkState
from background_services.notifications import NotificationLevel
from core.service import LoopService, ServiceState

#: Where the announced versions are persisted. One row in `app_state`, which
#: `LocalCache` already owns -- no new table, no second store.
ANNOUNCED_VERSIONS_KEY = "updates.announced_versions"


def _version_tuple(value: Optional[str]) -> Optional[tuple]:
    """Parse `major.minor.patch` for comparison, or None if it is not that.

    Strict, and deliberately so: `version.py` guarantees this exact shape, so
    anything else came from somewhere that cannot be reasoned about, and
    ordering it numerically would be a guess.
    """
    if not value:
        return None
    parts = str(value).strip().split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def newer_than_installed(versions: List[str], installed: str) -> List[str]:
    """The recorded versions that are strictly newer than the running build.

    This is the whole badge rule. Because the answer is recomputed from the
    installed version every time, upgrading empties it without any explicit
    acknowledgement step -- and a version that is no longer newer can never
    linger as a stale "1".
    """
    current = _version_tuple(installed)
    if current is None:
        return []
    newer = [v for v in versions if (_version_tuple(v) or ()) > current]
    return sorted(set(newer), key=lambda v: _version_tuple(v) or ())


class UpdateService(LoopService):
    """
    Periodically asks the backend whether a newer release exists.

    Signals:
        update_available(str, str) — version, download URL ("" if none was
            given). Emitted only on a change of announced version.
    """

    name = "updates"

    update_available = Signal(str, str)
    #: Number of announced versions newer than the installed one. Emitted only
    #: when the number actually changes, so the menu badge is repainted on a
    #: transition rather than on every poll.
    pending_count_changed = Signal(int)

    #: Cadence once a check has succeeded. A release is a human-scale event;
    #: polling faster buys nothing and costs a request per client per interval.
    CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000       # 6 hours
    #: Cadence while holding (offline, signed out, or the endpoint is absent).
    HOLD_INTERVAL_MS = 5 * 60 * 1000             # 5 minutes
    #: Cadence after a check failed for any other reason.
    error_interval_ms = 15 * 60 * 1000           # 15 minutes
    #: The first check runs a short delay after start rather than immediately:
    #: at startup the session is still being restored and the first probe has
    #: not run, so an immediate check would almost always hold anyway.
    FIRST_CHECK_DELAY_MS = 30 * 1000

    interval_ms = CHECK_INTERVAL_MS

    #: One request with TIMEOUT_FAST (5s) is the whole blocking budget.
    stop_timeout_ms = 8000

    def __init__(self, runtime, update_api: UpdateApiService, cache=None, parent=None) -> None:
        super().__init__(runtime, parent)
        self._update_api = update_api
        self._cache = cache if cache is not None else getattr(runtime, "cache", None)
        self._first_check_done = False
        #: The version this session has already *toasted* about. Holding it is
        #: what makes the notification edge-triggered. Separate from the
        #: persisted record below: the toast is per session, the badge is not.
        self._announced_version: Optional[str] = None
        #: Every version the backend has announced to this installation,
        #: including ones already installed since. Pruned only against the
        #: running version, never trimmed on a guess.
        self._announced_versions: List[str] = []
        #: Published badge count. Read from the GUI thread, written from the
        #: service thread -- a plain int assignment, which is why the list
        #: above is never exposed directly.
        self._pending_count = 0
        #: Last successful answer, for the UI and diagnostics.
        self._latest: Optional[Dict[str, Any]] = None

    # ── Public state ──────────────────────────────────────────────────────────

    @property
    def pending_count(self) -> int:
        """How many announced versions are newer than the installed build.

        0 means "nothing known to be pending", which includes the case where
        no check has succeeded yet. Safe to read from any thread.
        """
        return self._pending_count

    def download_url(self) -> Optional[str]:
        """Where to get the newest announced release, if the backend said.

        None when the deployment published no download URL — the caller must
        then say so rather than opening an empty page.
        """
        if not self._latest:
            return None
        return self._latest.get("download_url") or None

    @property
    def latest_release(self) -> Optional[Dict[str, Any]]:
        """The backend's last successful answer, or None if none succeeded.

        None means "not known yet", which is not the same as "up to date";
        callers that display this must say so rather than claiming currency
        the client has not established.
        """
        return self._latest

    def check_now(self) -> None:
        """Request an immediate check (safe from any thread)."""
        self.wake()

    def reset_session(self) -> None:
        """Forget what was announced, on logout.

        The next user gets the announcement in their own session rather than
        inheriting an "already told them" flag from the previous one. The
        badge is cleared with it, because the menu it hangs off belongs to the
        session that is ending; the durable record survives, so the next
        successful check restores the count without waiting for the backend to
        announce anything new.
        """
        self._announced_version = None
        self._latest = None
        self._first_check_done = False
        self._publish_count(0)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_announced_versions(self) -> List[str]:
        """Read the durable record. Never raises: a missing or corrupt row
        means "nothing recorded", which is a worse badge, not a broken app."""
        if self._cache is None:
            return []
        try:
            stored = self._cache.load_app_state(ANNOUNCED_VERSIONS_KEY)
        except Exception:  # noqa: BLE001
            self.log.exception("could not read the announced-version record")
            return []
        if not isinstance(stored, list):
            return []
        return [str(item) for item in stored if _version_tuple(item) is not None]

    def _save_announced_versions(self) -> None:
        if self._cache is None:
            return
        try:
            self._cache.save_app_state(ANNOUNCED_VERSIONS_KEY, self._announced_versions)
        except Exception:  # noqa: BLE001
            self.log.exception("could not record the announced version")

    def _recount(self) -> int:
        """Recompute the badge from the record and the installed version."""
        return len(newer_than_installed(self._announced_versions, version.VERSION))

    def _publish_count(self, count: int) -> None:
        """Emit only on a change. A count re-emitted on every poll would be
        the level-triggered signal this project has already been burned by."""
        if count == self._pending_count:
            return
        self._pending_count = count
        self.log.info("pending update count is now %d", count)
        self.pending_count_changed.emit(count)

    def on_start(self) -> None:
        """Publish the badge before the loop begins.

        Read here, on the GUI thread, rather than in the constructor: the
        runtime's construction does no I/O beyond opening the database, and
        waiting for the first check (30s in) would leave a user who restarted
        specifically to deal with an update looking at an empty menu.
        """
        self._announced_versions = self._load_announced_versions()
        # A record kept only of versions still ahead of us: once the user has
        # updated, the old entries have served their purpose and keeping them
        # would grow one row forever.
        pruned = newer_than_installed(self._announced_versions, version.VERSION)
        if pruned != self._announced_versions:
            self._announced_versions = pruned
            self._save_announced_versions()
        self._publish_count(len(pruned))
        super().on_start()

    def _record_version(self, announced: str) -> None:
        """Add a newly announced version to the durable record."""
        if announced in self._announced_versions:
            return
        self._announced_versions = newer_than_installed(
            self._announced_versions + [announced], version.VERSION
        )
        self._save_announced_versions()

    # ── Loop ──────────────────────────────────────────────────────────────────

    def _should_hold(self) -> Optional[str]:
        """A reason to skip this check, or None to proceed."""
        api_client = getattr(self.runtime, "api_client", None)
        if api_client is None or not api_client.access_token:
            return "not signed in"
        network = getattr(self.runtime, "network", None)
        if network is not None and network.network_state not in NetworkState.WORTH_TRYING:
            return f"network {network.network_state}"
        return None

    def tick(self) -> Optional[int]:
        if not self._first_check_done:
            # Give startup room to restore the session and run its first probe.
            self._first_check_done = True
            return self.FIRST_CHECK_DELAY_MS

        hold_reason = self._should_hold()
        if hold_reason:
            self.log.debug("update check held: %s", hold_reason)
            return self.HOLD_INTERVAL_MS

        try:
            payload = self._update_api.get_latest_version()
        except ApiError as exc:
            # Never surfaced to the user and never allowed to degrade anything:
            # not knowing whether an update exists is not a problem the person
            # tracking time can act on.
            self.log.info("update check unavailable: %s", exc)
            self.heartbeat(success=False)
            return self._jittered(self.HOLD_INTERVAL_MS)

        self._latest = payload
        self.heartbeat()
        if self.state == ServiceState.DEGRADED:
            self._set_state(ServiceState.RUNNING)

        # Recording and announcing are separate on purpose. The badge is
        # durable and survives a restart; the toast fires once per version per
        # session. A user who dismissed the toast still has the menu entry.
        self._record(payload)
        self._announce(payload)
        return self._jittered(self.CHECK_INTERVAL_MS)

    def _record(self, payload: Dict[str, Any]) -> None:
        """Persist an announced version and republish the badge count."""
        if not payload.get("update_available"):
            # The backend is offering this client nothing -- either it is
            # current, or the deployment has withdrawn what it was offering by
            # clearing DESKTOP_LATEST_VERSION. Both mean the record is stale,
            # and it is *dropped*, not merely recounted.
            #
            # Recounting is not enough, and getting this wrong would have
            # broken the rollback story outright: a withdrawn release is still
            # numerically newer than the installed build, so the badge would
            # have kept pointing users at a build that had just been pulled --
            # and, since the download URL is withdrawn with it, at nothing at
            # all. The withdrawal lever has to clear the badge as well as the
            # toast, or it only half works.
            self._forget_announced_versions()
            return
        latest = payload.get("latest_version")
        if latest and _version_tuple(latest) is not None:
            self._record_version(latest)
        self._publish_count(self._recount())

    def _forget_announced_versions(self) -> None:
        """Drop the durable record; the backend is offering nothing."""
        if self._announced_versions:
            self._announced_versions = []
            self._save_announced_versions()
        # The toast gate goes with it, so a release that is withdrawn and then
        # re-published announces itself again rather than being silently
        # swallowed as "already told them".
        self._announced_version = None
        self._publish_count(0)

    def _announce(self, payload: Dict[str, Any]) -> None:
        """Tell the user about a newer release, at most once per version."""
        if not payload.get("update_available"):
            return
        version = payload.get("latest_version")
        if not version or version == self._announced_version:
            # Either the deployment does not know its latest release, or this
            # session has already said so. Both are silence, not a repeat.
            return

        self._announced_version = version
        download_url = payload.get("download_url") or ""
        self.log.info("update available: %s", version)
        self.update_available.emit(version, download_url)

        notifications = getattr(self.runtime, "notifications", None)
        if notifications is None:
            return
        # A platform toast renders plain text, so the URL in the body is not
        # a link. `link` is what makes the notification actionable: clicking
        # the toast opens the download page. Without it the user is told an
        # update exists, and the address disappears the moment they click.
        message = f"Monitra {version} is available."
        message += (
            " Click here to download it."
            if download_url
            else " Ask your administrator where to download it."
        )
        # `notify` is safe from any thread: it hops to the notification
        # service's own thread through a queued signal.
        notifications.notify(
            message,
            NotificationLevel.INFO,
            title="Update available",
            key=f"update-available:{version}",
            link=download_url or None,
        )

    @staticmethod
    def _jittered(interval_ms: int) -> int:
        """Spread a fleet's checks out so they do not arrive in lockstep."""
        return int(interval_ms * (0.85 + random.random() * 0.3))
