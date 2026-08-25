import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from PySide6.QtCore import QObject, QTimer
from tracking.manager import BaseTracker
from tracking.active_window import get_active_window_info

class AppUsageTracker(BaseTracker):
    """
    Sub-tracker plugin that runs when a tracking session is active.
    Periodically checks the active window, aggregates duration, and
    saves segments to local SQLite cache database.
    """
    def __init__(self, local_cache, parent: Optional[QObject] = None) -> None:
        super().__init__()
        self.local_cache = local_cache
        self._time_entry_id: Optional[int] = None
        
        # Core active tracker state
        self._current_app: Optional[str] = None
        self._current_title: Optional[str] = None
        self._segment_start: Optional[float] = None
        self._segment_recorded_at: Optional[str] = None

        # Sample timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._sample)
        
        # Configurable intervals (seconds)
        self.SAMPLE_INTERVAL = 2.0
        self.MAX_ACCUMULATION = 10.0

    def start_tracker(self, session_data: Dict[str, Any]) -> None:
        self._time_entry_id = session_data.get("entry_id")
        if not self._time_entry_id:
            return

        self._current_app = None
        self._current_title = None
        self._segment_start = None
        self._segment_recorded_at = None

        # Start checking foreground window
        self._timer.start(int(self.SAMPLE_INTERVAL * 1000))
        self._sample()

    def stop_tracker(self) -> None:
        self._timer.stop()
        self._finalize_current_segment()
        self._time_entry_id = None

    def _sample(self) -> None:
        if not self._time_entry_id:
            return

        app_name, window_title = get_active_window_info()
        now = time.monotonic()

        # If it is the start of a tracking session
        if self._segment_start is None:
            self._current_app = app_name
            self._current_title = window_title
            self._segment_start = now
            self._segment_recorded_at = datetime.now(timezone.utc).isoformat()
            return

        # Check if the active window or app name changed
        changed = (app_name != self._current_app) or (window_title != self._current_title)
        elapsed = now - self._segment_start

        # If it changed or reached maximum aggregation flush limit
        if changed or elapsed >= self.MAX_ACCUMULATION:
            # Save the current segment
            self._save_segment(self._current_app, self._current_title, int(elapsed), self._segment_recorded_at)
            
            # Start new segment tracking
            self._current_app = app_name
            self._current_title = window_title
            self._segment_start = now
            self._segment_recorded_at = datetime.now(timezone.utc).isoformat()

    def _finalize_current_segment(self) -> None:
        if self._segment_start is not None and self._time_entry_id is not None:
            elapsed = time.monotonic() - self._segment_start
            if elapsed > 0:
                self._save_segment(self._current_app, self._current_title, int(elapsed), self._segment_recorded_at)
        self._current_app = None
        self._current_title = None
        self._segment_start = None
        self._segment_recorded_at = None

    def _save_segment(self, app_name: str, window_title: Optional[str], duration: int, recorded_at: str) -> None:
        if duration <= 0:
            return
        if not self._time_entry_id:
            return
        # Save to SQLite
        try:
            self.local_cache.save_app_usage(
                time_entry_id=self._time_entry_id,
                application_name=app_name,
                window_title=window_title,
                duration_seconds=duration,
                recorded_at=recorded_at
            )
        except Exception:
            # Don't let SQLite errors crash the sampler loop
            pass
