"""
activity_service — Captures, aggregates and persists user activity.

Completes the pipeline the audit found missing end to end:

    OS input (input_probe)
      -> per-second sampling            [this service, own thread]
      -> fixed aggregation window       [this service]
      -> activity_samples table         [storage]
      -> sync batch upload              [SyncService, when the backend
                                         exposes an endpoint]
      -> UI / screenshot binding        [activity percentage query]

The percentage is `active_seconds / window_seconds`, computed from what was
actually sampled. It is never fabricated: if input detection is unsupported on
the platform, windows are marked unmeasured and the UI shows "unavailable"
rather than a number, and if no timer is running nothing is recorded at all.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from PySide6.QtCore import Signal

from background_services.activity.input_probe import InputProbe
from core.service import LoopService


class ActivityService(LoopService):
    """
    Samples user input once per second while a timer is running and flushes an
    aggregated window to storage every `WINDOW_SECONDS`.

    Signals:
        activity_window_recorded(dict) — one completed window
        activity_percent_changed(int)  — current session percentage
    """

    name = "activity"

    activity_window_recorded = Signal(dict)
    activity_percent_changed = Signal(int)

    #: Sampling cadence. One second is fine: the probe is two cheap syscalls.
    SAMPLE_INTERVAL_MS = 1000
    #: Aggregation window flushed to storage.
    WINDOW_SECONDS = 60

    def __init__(self, runtime, cache, parent=None) -> None:
        super().__init__(runtime, parent)
        self._cache = cache
        self._probe = InputProbe()
        self.interval_ms = self.SAMPLE_INTERVAL_MS

        self._entry_id: Optional[int] = None
        #: True between start_tracker() and stop_tracker(). Sampling is gated
        #: on this rather than on `_entry_id`, so a session that begins offline
        #: (and therefore has no backend entry id yet) is still measured.
        self._tracking = False
        self._window_start: Optional[str] = None
        self._sampled = 0
        self._active = 0
        self._key_events = 0
        self._mouse_events = 0

    # ── Introspection ─────────────────────────────────────────────────────────

    @property
    def supported(self) -> bool:
        """Whether this platform can measure activity at all."""
        return self._probe.supported

    def current_percent(self) -> int:
        """Activity percentage for the window currently being accumulated."""
        if self._sampled <= 0:
            return 0
        return max(0, min(100, round(self._active / self._sampled * 100)))

    def percent_for_entry(self, entry_id: int) -> int:
        """Duration-weighted activity percentage for a completed time entry."""
        try:
            return self._cache.get_activity_percent_for_entry(entry_id)
        except Exception:  # noqa: BLE001
            self.log.exception("could not read activity for entry %s", entry_id)
            return 0

    # ── Window management ─────────────────────────────────────────────────────

    def _reset_window(self) -> None:
        self._window_start = datetime.now(timezone.utc).isoformat()
        self._sampled = 0
        self._active = 0
        self._key_events = 0
        self._mouse_events = 0

    def _flush_window(self) -> None:
        """Persist the accumulated window, if it measured anything."""
        if self._sampled <= 0 or self._window_start is None:
            self._reset_window()
            return

        if self._entry_id is None:
            # The backend has not issued an entry id yet — the session was
            # started offline, or the start request is still in flight. Keep
            # accumulating rather than discarding: the counters are two
            # integers, so holding the window costs nothing, and the window
            # will be attributed correctly once `bind_entry_id` arrives.
            # Resetting here silently dropped every minute of activity
            # measured before the backend replied.
            self.log.debug(
                "holding a %ds activity window until a time entry id is available",
                self._sampled,
            )
            return
        record = {
            "time_entry_id": self._entry_id,
            "window_start": self._window_start,
            "window_seconds": self._sampled,
            "active_seconds": self._active,
            "key_events": self._key_events,
            "mouse_events": self._mouse_events,
            "activity_percent": self.current_percent(),
        }
        try:
            self._cache.save_activity_sample(
                time_entry_id=self._entry_id,
                window_start=self._window_start,
                window_seconds=self._sampled,
                active_seconds=self._active,
                key_events=self._key_events,
                mouse_events=self._mouse_events,
            )
        except Exception:  # noqa: BLE001
            self.log.exception("could not persist activity window")
        else:
            self.log.info(
                "activity window: %d/%ds active (%d%%) for entry %s",
                self._active, self._sampled, record["activity_percent"], self._entry_id,
            )
            self.activity_window_recorded.emit(record)
        self._reset_window()

    # ── Tracker interface (driven by TimerService) ────────────────────────────

    def start_tracker(self, session: Dict[str, Any]) -> None:
        """Begin capturing for a tracking session."""
        self._entry_id = session.get("entry_id")
        self._tracking = True
        self._reset_window()
        self.log.info(
            "activity capture started for entry %s (probe supported=%s)",
            self._entry_id, self._probe.supported,
        )

    def bind_entry_id(self, entry_id: int) -> None:
        """
        Attach a backend entry id that arrived after tracking began.

        Windows sampled before the backend replied are retained and attributed
        to this entry, so the first minute of a session is not lost.
        """
        self._entry_id = entry_id

    def stop_tracker(self) -> None:
        """Flush the partial window and stop capturing."""
        self._flush_window()
        self._tracking = False
        self._entry_id = None
        self._window_start = None

    # ── Loop ──────────────────────────────────────────────────────────────────

    def tick(self) -> Optional[int]:
        # Only measure while a session is being tracked; otherwise idle cheaply.
        if not self._tracking:
            return self.SAMPLE_INTERVAL_MS

        if self._entry_id is None:
            # A session is running but has no backend id yet (started offline,
            # or the start is still in flight). Sample anyway and attribute the
            # window when `bind_entry_id` arrives — activity measured during an
            # outage is exactly the activity we must not lose.
            session = self.runtime.timer.active_session() or {}
            self._entry_id = session.get("entry_id")

        sample = self._probe.sample(self.SAMPLE_INTERVAL_MS / 1000.0 * 1.5)
        if sample is None:
            # Unsupported platform: record nothing rather than invent a value.
            return self.SAMPLE_INTERVAL_MS

        self._sampled += 1
        if sample["active"]:
            self._active += 1
        if sample["mouse"]:
            self._mouse_events += 1
        if sample["keyboard"]:
            self._key_events += 1

        self.heartbeat()

        if self._sampled >= self.WINDOW_SECONDS:
            self._flush_window()
        elif self._sampled % 5 == 0:
            self.activity_percent_changed.emit(self.current_percent())

        return self.SAMPLE_INTERVAL_MS

    def on_stop(self, timeout_ms: int) -> bool:
        self._flush_window()
        return super().on_stop(timeout_ms)
