"""
url_usage_service — Tracks real-time browser URL usage while a timer is active.

Subclasses `LoopService` (QObject + moveToThread + QTimer) running on a
dedicated service thread. Driven by `TimerService` lifecycle hooks.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.service import LoopService
from tracking.active_window import get_active_window_info
from tracking.browsers import get_browser_manager


class UrlUsageService(LoopService):
    """Samples active browser URL usage while a tracking session is active."""

    name = "url_usage"

    #: How often the active browser URL is sampled.
    SAMPLE_INTERVAL_MS = 2000
    #: Maximum continuous session duration before flushing an incremental segment.
    MAX_SEGMENT_SECONDS = 60.0
    #: Maximum allowed gap between samples before treating it as a resume after sleep.
    MAX_OBSERVATION_GAP_SECONDS = 30.0
    #: Idle cadence when not tracking.
    IDLE_INTERVAL_MS = 5000

    def __init__(self, runtime, cache, parent=None) -> None:
        super().__init__(runtime, parent)
        self._cache = cache
        self.interval_ms = self.IDLE_INTERVAL_MS
        self._browser_manager = get_browser_manager()

        self._entry_id: Optional[int] = None
        self._tracking = False

        # Current URL session state
        self._current_browser: Optional[str] = None
        self._current_domain: Optional[str] = None
        self._current_url: Optional[str] = None
        self._current_title: Optional[str] = None
        self._current_client_event_id: Optional[str] = None
        self._session_start: Optional[float] = None
        self._last_observed: Optional[float] = None
        self._session_recorded_at: Optional[str] = None

    # ── Tracker interface (driven by TimerService) ────────────────────────────

    def start_tracker(self, session: Dict[str, Any]) -> None:
        self._entry_id = session.get("entry_id")
        self._tracking = True
        self._reset_session()
        self.log.info("browser URL usage tracking started for entry %s", self._entry_id)
        self.wake()

    def bind_entry_id(self, entry_id: int) -> None:
        """Attribute in-progress URL sessions to a late-arriving entry id."""
        self._entry_id = entry_id

    def stop_tracker(self) -> None:
        self._flush_session()
        self._tracking = False
        self._entry_id = None
        self._reset_session()
        self.log.info("browser URL usage tracking stopped")

    # ── Session lifecycle ─────────────────────────────────────────────────────

    def _reset_session(self) -> None:
        self._current_browser = None
        self._current_domain = None
        self._current_url = None
        self._current_title = None
        self._current_client_event_id = None
        self._session_start = None
        self._last_observed = None
        self._session_recorded_at = None

    def _flush_session(self) -> None:
        if (
            self._session_start is None or
            self._last_observed is None or
            self._entry_id is None or
            not self._current_browser or
            not self._current_domain
        ):
            return

        duration = int(self._last_observed - self._session_start)
        if duration <= 0:
            return

        client_event_id = self._current_client_event_id or str(uuid.uuid4())
        try:
            self._cache.save_url_usage(
                time_entry_id=self._entry_id,
                browser_name=self._current_browser,
                domain=self._current_domain,
                url=self._current_url,
                page_title=self._current_title,
                duration_seconds=duration,
                recorded_at=self._session_recorded_at or datetime.now(timezone.utc).isoformat(),
                client_event_id=client_event_id,
            )
        except Exception:  # noqa: BLE001
            self.log.exception("could not persist browser URL usage session")
        else:
            self.log.debug(
                "url usage session flushed: %s - %s (%ds)",
                self._current_browser, self._current_domain, duration
            )

    def _begin_session(
        self,
        browser_name: str,
        domain: str,
        url: Optional[str],
        title: Optional[str],
        now: float
    ) -> None:
        self._current_browser = browser_name
        self._current_domain = domain
        self._current_url = url
        self._current_title = title
        self._current_client_event_id = str(uuid.uuid4())
        self._session_start = now
        self._last_observed = now
        self._session_recorded_at = datetime.now(timezone.utc).isoformat()

    # ── Loop tick ─────────────────────────────────────────────────────────────

    def tick(self) -> Optional[int]:
        if not self._tracking:
            return self.IDLE_INTERVAL_MS

        if self._entry_id is None:
            session = self.runtime.timer.active_session() or {}
            self._entry_id = session.get("entry_id")

        app_name, window_title = get_active_window_info()
        now = time.monotonic()

        # Check if current active window is a supported browser
        browser_info = self._browser_manager.extract_browser_info(app_name, window_title)

        if browser_info is None:
            # User switched to a non-browser application (e.g. VS Code, Slack)
            if self._session_start is not None:
                self._flush_session()
                self._reset_session()
            self.heartbeat()
            return self.SAMPLE_INTERVAL_MS

        browser_name, domain, url, page_title = browser_info

        if self._session_start is None:
            self._begin_session(browser_name, domain, url, page_title, now)
            self.heartbeat()
            return self.SAMPLE_INTERVAL_MS

        # Check if URL session has changed
        same_session = (
            browser_name == self._current_browser and
            domain == self._current_domain and
            url == self._current_url
        )

        gap = now - (self._last_observed or now)
        elapsed = now - self._session_start

        if not same_session or gap > self.MAX_OBSERVATION_GAP_SECONDS or elapsed >= self.MAX_SEGMENT_SECONDS:
            self._flush_session()
            self._begin_session(browser_name, domain, url, page_title, now)
        else:
            self._last_observed = now
            if page_title and not self._current_title:
                self._current_title = page_title

        self.heartbeat()
        return self.SAMPLE_INTERVAL_MS

    def on_stop(self, timeout_ms: int) -> bool:
        self._flush_session()
        return super().on_stop(timeout_ms)
