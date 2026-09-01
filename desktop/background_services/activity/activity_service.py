"""
activity_service — Captures, aggregates and persists user activity.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from PySide6.QtCore import Signal

from background_services.activity.input_probe import InputProbe
from core.service import LoopService


# Configurable Thresholds & Weights for normalized Activity % calculation
MAX_KEYBOARD_STROKES_PER_INTERVAL = 120
MAX_MOUSE_CLICKS_PER_INTERVAL = 30
MAX_MOUSE_MOVEMENTS_PER_INTERVAL = 400

KEYBOARD_WEIGHT = 0.40
MOUSE_CLICK_WEIGHT = 0.30
MOUSE_MOVEMENT_WEIGHT = 0.30


def calculate_activity_percentage(
    keyboard_strokes: int,
    mouse_clicks: int,
    mouse_movements: int,
    active_seconds: int = 0,
    window_seconds: int = 60
) -> int:
    """Calculate normalized activity percentage (0-100) from counters or sampled active time."""
    if keyboard_strokes > 0 or mouse_clicks > 0 or mouse_movements > 0:
        k_score = min(max(0, keyboard_strokes) / MAX_KEYBOARD_STROKES_PER_INTERVAL, 1.0)
        c_score = min(max(0, mouse_clicks) / MAX_MOUSE_CLICKS_PER_INTERVAL, 1.0)
        m_score = min(max(0, mouse_movements) / MAX_MOUSE_MOVEMENTS_PER_INTERVAL, 1.0)

        total_score = (
            k_score * KEYBOARD_WEIGHT
            + c_score * MOUSE_CLICK_WEIGHT
            + m_score * MOUSE_MOVEMENT_WEIGHT
        )
        return max(0, min(100, round(total_score * 100)))

    if window_seconds > 0:
        return max(0, min(100, round(active_seconds / window_seconds * 100)))

    return 0


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

    SAMPLE_INTERVAL_MS = 1000
    WINDOW_SECONDS = 60

    def __init__(self, runtime, cache, parent=None) -> None:
        super().__init__(runtime, parent)
        self._cache = cache
        self._probe = InputProbe()
        self.interval_ms = self.SAMPLE_INTERVAL_MS

        self._entry_id: Optional[int] = None
        self._tracking = False
        self._window_start: Optional[str] = None
        self._sampled = 0
        self._active = 0
        self._key_events = 0
        self._mouse_events = 0
        self._keyboard_strokes = 0
        self._mouse_clicks = 0
        self._mouse_movements = 0

    @property
    def supported(self) -> bool:
        return self._probe.supported

    def current_percent(self) -> int:
        return calculate_activity_percentage(
            self._keyboard_strokes,
            self._mouse_clicks,
            self._mouse_movements,
            self._active,
            max(1, self._sampled)
        )

    def percent_for_entry(self, entry_id: int) -> int:
        try:
            return self._cache.get_activity_percent_for_entry(entry_id)
        except Exception:  # noqa: BLE001
            self.log.exception("could not read activity for entry %s", entry_id)
            return 0

    def _reset_window(self) -> None:
        self._window_start = datetime.now(timezone.utc).isoformat()
        self._sampled = 0
        self._active = 0
        self._key_events = 0
        self._mouse_events = 0
        self._keyboard_strokes = 0
        self._mouse_clicks = 0
        self._mouse_movements = 0

    def _flush_window(self) -> None:
        if self._sampled <= 0 or self._window_start is None:
            self._reset_window()
            return

        if self._entry_id is None:
            self.log.debug(
                "holding a %ds activity window until a time entry id is available",
                self._sampled,
            )
            return

        act_percent = self.current_percent()
        record = {
            "time_entry_id": self._entry_id,
            "window_start": self._window_start,
            "window_seconds": self._sampled,
            "active_seconds": self._active,
            "key_events": self._key_events,
            "mouse_events": self._mouse_events,
            "keyboard_strokes": self._keyboard_strokes,
            "mouse_clicks": self._mouse_clicks,
            "mouse_movements": self._mouse_movements,
            "activity_percent": act_percent,
        }
        try:
            self._cache.save_activity_sample(
                time_entry_id=self._entry_id,
                window_start=self._window_start,
                window_seconds=self._sampled,
                active_seconds=self._active,
                key_events=self._key_events,
                mouse_events=self._mouse_events,
                keyboard_strokes=self._keyboard_strokes,
                mouse_clicks=self._mouse_clicks,
                mouse_movements=self._mouse_movements,
                activity_percent=act_percent,
            )
        except Exception:  # noqa: BLE001
            self.log.exception("could not persist activity window")
        else:
            self.log.info(
                "activity window: %d/%ds active (%d%%, keys=%d, clicks=%d, moves=%d) for entry %s",
                self._active, self._sampled, act_percent,
                self._keyboard_strokes, self._mouse_clicks, self._mouse_movements,
                self._entry_id,
            )
            self.activity_window_recorded.emit(record)
        self._reset_window()

    def start_tracker(self, session: Dict[str, Any]) -> None:
        self._entry_id = session.get("entry_id")
        self._tracking = True
        self._reset_window()
        self.log.info(
            "activity capture started for entry %s (probe supported=%s)",
            self._entry_id, self._probe.supported,
        )

    def bind_entry_id(self, entry_id: int) -> None:
        self._entry_id = entry_id

    def stop_tracker(self) -> None:
        self._flush_window()
        self._tracking = False
        self._entry_id = None
        self._window_start = None

    def tick(self) -> Optional[int]:
        if not self._tracking:
            return self.SAMPLE_INTERVAL_MS

        if self._entry_id is None:
            session = self.runtime.timer.active_session() or {}
            self._entry_id = session.get("entry_id")

        sample = self._probe.sample(self.SAMPLE_INTERVAL_MS / 1000.0 * 1.5)
        if sample is None:
            return self.SAMPLE_INTERVAL_MS

        self._sampled += 1
        if sample.get("active"):
            self._active += 1
        if sample.get("mouse"):
            self._mouse_events += 1
        if sample.get("keyboard"):
            self._key_events += 1

        self._keyboard_strokes += sample.get("keyboard_strokes", 0)
        self._mouse_clicks += sample.get("mouse_clicks", 0)
        self._mouse_movements += sample.get("mouse_movements", 0)

        self.heartbeat()

        if self._sampled >= self.WINDOW_SECONDS:
            self._flush_window()
        elif self._sampled % 5 == 0:
            self.activity_percent_changed.emit(self.current_percent())

        return self.SAMPLE_INTERVAL_MS

    def on_stop(self, timeout_ms: int) -> bool:
        self._flush_window()
        return super().on_stop(timeout_ms)
