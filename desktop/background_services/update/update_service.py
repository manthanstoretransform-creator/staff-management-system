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
"""
from __future__ import annotations

import random
from typing import Any, Dict, Optional

from PySide6.QtCore import Signal

from app.api.exceptions import ApiError
from app.updates.service import UpdateApiService
from background_services.network import NetworkState
from background_services.notifications import NotificationLevel
from core.service import LoopService, ServiceState


class UpdateService(LoopService):
    """
    Periodically asks the backend whether a newer release exists.

    Signals:
        update_available(str, str) — version, download URL ("" if none was
            given). Emitted only on a change of announced version.
    """

    name = "updates"

    update_available = Signal(str, str)

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

    def __init__(self, runtime, update_api: UpdateApiService, parent=None) -> None:
        super().__init__(runtime, parent)
        self._update_api = update_api
        self._first_check_done = False
        #: The version this session has already told the user about. Holding it
        #: is what makes the announcement edge-triggered.
        self._announced_version: Optional[str] = None
        #: Last successful answer, for the UI and diagnostics.
        self._latest: Optional[Dict[str, Any]] = None

    # ── Public state ──────────────────────────────────────────────────────────

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
        inheriting a "already told them" flag from the previous one.
        """
        self._announced_version = None
        self._latest = None
        self._first_check_done = False

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

        self._announce(payload)
        return self._jittered(self.CHECK_INTERVAL_MS)

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
        message = f"Monitra {version} is available."
        if download_url:
            message += f" Download it from {download_url}"
        # `notify` is safe from any thread: it hops to the notification
        # service's own thread through a queued signal.
        notifications.notify(
            message,
            NotificationLevel.INFO,
            title="Update available",
            key=f"update-available:{version}",
        )

    @staticmethod
    def _jittered(interval_ms: int) -> int:
        """Spread a fleet's checks out so they do not arrive in lockstep."""
        return int(interval_ms * (0.85 + random.random() * 0.3))
