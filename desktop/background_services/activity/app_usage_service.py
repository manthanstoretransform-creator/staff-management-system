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
    #: A gap larger than this between samples means the machine was asleep or
    #: the loop was stalled. That time was never observed, so it is not
    #: claimed: the segment is closed at the last real observation.
    MAX_OBSERVATION_GAP_SECONDS = 30.0

    def __init__(self, runtime, cache, parent=None) -> None:
        super().__init__(runtime, parent)
        self._cache = cache
        self.interval_ms = self.IDLE_INTERVAL_MS

        self._entry_id: Optional[int] = None
        self._tracking = False
        self._current_app: Optional[str] = None
        self._current_title: Optional[str] = None
        self._segment_start: Optional[float] = None
        self._last_observed: Optional[float] = None
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

    def _observe_now(self) -> None:
        """Count the time up to this instant as observed.

        Used when the tracking session ends: the user really was in the
        current application right up to the moment they stopped the timer, so
        the trailing part-interval since the last sample belongs in the
        segment. It is only claimed if the loop was actually alive over that
        stretch -- an unobserved gap (sleep, stall) is still discarded.
        """
        base = self._last_observed if self._last_observed is not None else self._segment_start
        if base is None:
            return
        now = time.monotonic()
        if now - base <= self.MAX_OBSERVATION_GAP_SECONDS:
            self._last_observed = now

    def stop_tracker(self) -> None:
        self._observe_now()
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
        self._last_observed = None
        self._segment_recorded_at = None

    def _flush_segment(self) -> None:
        if self._segment_start is None or self._entry_id is None or not self._current_app:
            return
        # Measured from the last sample that actually observed this
        # application, not from "now". Reading the clock at flush time
        # silently absorbed any gap since the last observation -- so a laptop
        # that slept for an hour with VS Code in front woke up and recorded
        # an hour of VS Code use that nobody performed.
        duration = int((self._last_observed or self._segment_start) - self._segment_start)
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
        self._last_observed = self._segment_start
        self._segment_recorded_at = datetime.now(timezone.utc).isoformat()

    # ── Loop ──────────────────────────────────────────────────────────────────

    def tick(self) -> Optional[int]:
        if not self._tracking:
            return self.IDLE_INTERVAL_MS

        if self._entry_id is None:
            session = self.runtime.timer.active_session() or {}
            self._entry_id = session.get("entry_id")

        app_name, window_title = get_active_window_info()
        now = time.monotonic()

        if self._segment_start is None:
            self._begin_segment(app_name, window_title)
            return self.SAMPLE_INTERVAL_MS

        # A segment is bounded by the *application*, not by the window title.
        # Keying it on the title too meant that typing in an editor, or a tab
        # switch in a browser, closed one segment and opened another every
        # two seconds: a stream of duplicate 2-second rows for one unbroken
        # stretch of work, each one a separate row to store, sync and render.
        changed = app_name != self._current_app
        elapsed = now - self._segment_start
        gap = now - (self._last_observed or now)

        if gap > self.MAX_OBSERVATION_GAP_SECONDS:
            # Unobserved time (sleep/stall). Close at the last real sample
            # and start again from this one rather than claiming the gap.
            self._flush_segment()
            self._begin_segment(app_name, window_title)
            self.heartbeat()
            return self.SAMPLE_INTERVAL_MS

        # This sample observed the current application; record that before
        # any early return, or a held-open segment would look stalled and
        # trip the gap check above on the next tick.
        self._last_observed = now

        if self._entry_id is None:
            # No backend entry id yet (started offline, or the start is still
            # in flight). Hold the current segment open rather than closing one
            # that cannot be persisted: `_flush_segment` would drop it and
            # `_begin_segment` would reset the clock, losing the elapsed time
            # entirely. Only a genuine application change forces a boundary,
            # and even then the unattributable part is knowingly discarded.
            if not changed:
                return self.SAMPLE_INTERVAL_MS

        if changed or elapsed >= self.MAX_SEGMENT_SECONDS:
            self._flush_segment()
            self._begin_segment(app_name, window_title)
        elif window_title and window_title != self._current_title:
            # Same application, new window title: keep the segment running
            # and let it carry the most recent title.
            self._current_title = window_title

        self.heartbeat()
        return self.SAMPLE_INTERVAL_MS

    def on_stop(self, timeout_ms: int) -> bool:
        self._observe_now()
        self._flush_segment()
        return super().on_stop(timeout_ms)
