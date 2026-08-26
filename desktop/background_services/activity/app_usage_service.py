"""
app_usage_service — Tracks which application the user is working in.

Replaces `tracking/app_usage_tracker.py`. The behaviour (sample the foreground
window, aggregate contiguous use into segments, flush segments to storage for
the sync service to upload) is preserved; the threading is not.

The previous tracker ran its sampling QTimer on the GUI thread and wrote to
SQLite from there, every two seconds, for the entire duration of a tracking
session — competing with the sync consumer for the same shared connection.
Here the sampling loop owns a service thread, and storage gives that thread its
own connection, so neither can stall the UI.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.service import LoopService
from tracking.active_window import get_active_window_info


class AppUsageService(LoopService):
    """Samples the foreground window while a tracking session is active."""

    name = "app_usage"

    #: How often the foreground window is sampled.
    SAMPLE_INTERVAL_MS = 2000
    #: A single unbroken segment is flushed at least this often, so a long
    #: session in one application still produces incremental records rather
    #: than one enormous record that is lost if the process dies.
    MAX_SEGMENT_SECONDS = 60.0
    #: Idle cadence when nothing is being tracked.
    IDLE_INTERVAL_MS = 5000

    def __init__(self, runtime, cache, parent=None) -> None:
        super().__init__(runtime, parent)
        self._cache = cache
        self.interval_ms = self.IDLE_INTERVAL_MS

        self._entry_id: Optional[int] = None
        self._tracking = False
        self._current_app: Optional[str] = None
        self._current_title: Optional[str] = None
        self._segment_start: Optional[float] = None
        self._segment_recorded_at: Optional[str] = None

    # ── Tracker interface (driven by TimerService) ────────────────────────────

    def start_tracker(self, session: Dict[str, Any]) -> None:
        self._entry_id = session.get("entry_id")
        self._tracking = True
        self._reset_segment()
        self.log.info("application usage tracking started for entry %s", self._entry_id)
        self.wake()

    def bind_entry_id(self, entry_id: int) -> None:
        """Attribute the in-progress segment to a late-arriving entry id."""
        self._entry_id = entry_id

    def stop_tracker(self) -> None:
        self._flush_segment()
        self._tracking = False
        self._entry_id = None
        self._reset_segment()
        self.log.info("application usage tracking stopped")

    # ── Segments ──────────────────────────────────────────────────────────────

    def _reset_segment(self) -> None:
        self._current_app = None
        self._current_title = None
        self._segment_start = None
        self._segment_recorded_at = None

    def _flush_segment(self) -> None:
        if self._segment_start is None or self._entry_id is None or not self._current_app:
            return
        duration = int(time.monotonic() - self._segment_start)
        if duration <= 0:
            return
        try:
            self._cache.save_app_usage(
                time_entry_id=self._entry_id,
                application_name=self._current_app,
                window_title=self._current_title,
                duration_seconds=duration,
                recorded_at=self._segment_recorded_at
                or datetime.now(timezone.utc).isoformat(),
            )
        except Exception:  # noqa: BLE001
            self.log.exception("could not persist application usage segment")
        else:
            self.log.debug("app usage segment: %s for %ds", self._current_app, duration)

    def _begin_segment(self, app_name: Optional[str], title: Optional[str]) -> None:
        self._current_app = app_name
        self._current_title = title
        self._segment_start = time.monotonic()
        self._segment_recorded_at = datetime.now(timezone.utc).isoformat()

    # ── Loop ──────────────────────────────────────────────────────────────────

    def tick(self) -> Optional[int]:
        if not self._tracking:
            return self.IDLE_INTERVAL_MS

        if self._entry_id is None:
            session = self.runtime.timer.active_session() or {}
            self._entry_id = session.get("entry_id")

        app_name, window_title = get_active_window_info()

        if self._segment_start is None:
            self._begin_segment(app_name, window_title)
            return self.SAMPLE_INTERVAL_MS

        changed = app_name != self._current_app or window_title != self._current_title
        elapsed = time.monotonic() - self._segment_start

        if changed or elapsed >= self.MAX_SEGMENT_SECONDS:
            self._flush_segment()
            self._begin_segment(app_name, window_title)

        self.heartbeat()
        return self.SAMPLE_INTERVAL_MS

    def on_stop(self, timeout_ms: int) -> bool:
        self._flush_segment()
        return super().on_stop(timeout_ms)
