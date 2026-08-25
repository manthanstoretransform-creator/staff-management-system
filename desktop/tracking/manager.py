import time
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from PySide6.QtCore import QObject, Signal, QTimer
from app.time_entries.service import TimeEntryService
from ui.workers import StartTimeEntryWorker, StopTimeEntryWorker

logger = logging.getLogger(__name__)


class BaseTracker(QObject):
    """
    Base interface class for future tracking modules (Screenshots, Apps, URLs, etc.).
    Allows plugging sub-trackers into the TrackingManager lifecycle cleanly.
    """
    def start_tracker(self, session_data: Dict[str, Any]) -> None:
        """Called when a tracking session starts."""
        pass

    def stop_tracker(self) -> None:
        """Called when a tracking session stops."""
        pass


class TrackingManager(QObject):
    """
    Central Manager responsible for the core time tracking lifecycle.
    Manages background API workers, handles active session state, provides a robust timer,
    and supports sub-tracker plugins for extensible tracking.
    """
    # Signals to communicate tracking lifecycle changes globally
    tracking_started = Signal(dict)   # session details (project_id, task_id, entry_id, start_time)
    tracking_stopped = Signal(dict)   # stop result from API
    tick = Signal(int)                # current elapsed seconds
    error_occurred = Signal(str)      # validation or backend API errors
    status_message = Signal(str)      # user-friendly status changes (e.g. "Starting...")

    def __init__(
        self,
        time_entry_service: TimeEntryService,
        local_cache = None,
        parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)
        self.time_entry_service = time_entry_service
        self.local_cache = local_cache

        # Active session tracking properties
        self._active_session: Optional[Dict[str, Any]] = None
        self._is_starting: bool = False
        self._is_stopping: bool = False
        self._is_switching_internal: bool = False

        # Real-time elapsed clock
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._start_monotonic: Optional[float] = None
        self._elapsed_offset: int = 0

        # Sub-tracker plugins registry
        self._trackers: List[BaseTracker] = []

        # References to background threads to prevent garbage collection
        self._start_worker: Optional[StartTimeEntryWorker] = None
        self._stop_worker: Optional[StopTimeEntryWorker] = None

    def register_tracker(self, tracker: BaseTracker) -> None:
        """Register a sub-tracker module to be controlled by this manager."""
        if tracker not in self._trackers:
            self._trackers.append(tracker)

    def is_tracking_active(self) -> bool:
        """Return True if a tracking session is actively running."""
        return self._active_session is not None

    def get_active_session(self) -> Optional[Dict[str, Any]]:
        """Return active session details, or None if inactive."""
        return self._active_session

    def get_elapsed_seconds(self) -> int:
        """Calculate elapsed seconds using monotonic time to avoid counter drift."""
        if not self.is_tracking_active() or self._start_monotonic is None:
            return 0
        return int(time.monotonic() - self._start_monotonic) + self._elapsed_offset

    def start_tracking(self, project_id: int, task_id: int, task_name: Optional[str] = None) -> None:
        """
        Verify no session is running, execute backend Time Entry API,
        and start tracking on success. If another task is already tracking,
        delegate to switch_tracking.
        """
        if self.is_tracking_active():
            active_task_id = self._active_session["task_id"]
            if active_task_id != task_id:
                self.switch_tracking(project_id, task_id, task_name)
            else:
                self.error_occurred.emit("This task is already being tracked.")
            return
        if self._is_starting:
            return  # Prevent duplicate start requests

        self._is_starting = True
        self.status_message.emit("Starting timer...")

        # Initialize start worker
        self._start_worker = StartTimeEntryWorker(self.time_entry_service, project_id, task_id)

        def on_start_success(entry_id: int) -> None:
            self._is_starting = False
            self._start_monotonic = time.monotonic()
            self._elapsed_offset = 0

            self._active_session = {
                "project_id": project_id,
                "task_id": task_id,
                "task_name": task_name,
                "entry_id": entry_id,
                "start_time": datetime.now(timezone.utc).isoformat()
            }

            # Start real-time elapsed timer
            self._timer.start(1000)

            # Persist running timer state in local SQLite cache
            self._persist_timer_state()

            # Start registered sub-trackers
            for tracker in self._trackers:
                try:
                    tracker.start_tracker(self._active_session)
                except Exception as e:
                    logger.error(f"Error starting sub-tracker: {e}", exc_info=True)

            self.tracking_started.emit(self._active_session)
            self.status_message.emit("Timer started")
            self._start_worker = None

        def on_start_error(msg: str) -> None:
            self._is_starting = False
            self.error_occurred.emit(msg)
            self.status_message.emit("Failed to start timer")
            self._start_worker = None

        self._start_worker.finished.connect(on_start_success)
        self._start_worker.error.connect(on_start_error)
        self._start_worker.finished.connect(self._start_worker.deleteLater)
        self._start_worker.error.connect(self._start_worker.deleteLater)
        self._start_worker.start()

    def switch_tracking(self, new_project_id: int, new_task_id: int, new_task_name: Optional[str] = None) -> None:
        """Atomic switch: stop current tracking session and start a new one."""
        if not self.is_tracking_active():
            self.start_tracking(new_project_id, new_task_id, new_task_name)
            return
        if self._is_stopping or self._is_starting:
            return  # Prevent parallel concurrent switches

        self._is_switching_internal = True
        self._is_stopping = True
        self.status_message.emit("Switching timer...")

        session = self._active_session
        old_entry_id = session["entry_id"]
        old_task_id = session["task_id"]
        elapsed = self.get_elapsed_seconds()

        # Stop local timer tick loop instantly
        self._timer.stop()

        # Stop sub-trackers for old session
        for tracker in self._trackers:
            try:
                tracker.stop_tracker()
            except Exception as e:
                logger.error(f"Error stopping sub-tracker: {e}", exc_info=True)

        self._stop_worker = StopTimeEntryWorker(self.time_entry_service, old_entry_id, self.local_cache)

        def on_stop_success(result: dict) -> None:
            self._is_stopping = False

            # Add elapsed time to local cache database for reports/history
            if self.local_cache and elapsed > 0:
                try:
                    today_str = datetime.now().date().isoformat()
                    self.local_cache.add_elapsed_to_cached_time_entry(today_str, old_task_id, elapsed)
                except Exception as e:
                    logger.error(f"Error saving elapsed duration: {e}")

            # Notify stops
            self.tracking_stopped.emit(result)

            # Clear session
            self._active_session = None
            self._start_monotonic = None
            self._elapsed_offset = 0

            # Now start new timer
            self._start_worker = StartTimeEntryWorker(self.time_entry_service, new_project_id, new_task_id)

            def on_start_success(entry_id: int) -> None:
                self._is_switching_internal = False
                self._start_monotonic = time.monotonic()
                self._elapsed_offset = 0

                self._active_session = {
                    "project_id": new_project_id,
                    "task_id": new_task_id,
                    "task_name": new_task_name,
                    "entry_id": entry_id,
                    "start_time": datetime.now(timezone.utc).isoformat(),
                    "is_switch": True
                }

                # Start real-time elapsed timer
                self._timer.start(1000)

                # Persist running timer state in local SQLite cache
                self._persist_timer_state()

                # Start registered sub-trackers
                for tracker in self._trackers:
                    try:
                        tracker.start_tracker(self._active_session)
                    except Exception as e:
                        logger.error(f"Error starting sub-tracker: {e}", exc_info=True)

                self.tracking_started.emit(self._active_session)
                self.status_message.emit("Timer switched")
                self._start_worker = None

            def on_start_error(msg: str) -> None:
                self._is_switching_internal = False
                self.error_occurred.emit(msg)
                self.status_message.emit("Failed to start new timer")
                self._start_worker = None

            self._start_worker.finished.connect(on_start_success)
            self._start_worker.error.connect(on_start_error)
            self._start_worker.finished.connect(self._start_worker.deleteLater)
            self._start_worker.error.connect(self._start_worker.deleteLater)
            self._start_worker.start()

            self._stop_worker = None

        def on_stop_error(msg: str) -> None:
            self._is_switching_internal = False
            self._is_stopping = False
            self._timer.start(1000)  # Resume tick loop for active session
            self.error_occurred.emit(f"Failed to stop current timer for switch: {msg}")
            self.status_message.emit("Failed to switch timer")
            self._stop_worker = None

        self._stop_worker.finished.connect(on_stop_success)
        self._stop_worker.error.connect(on_stop_error)
        self._stop_worker.finished.connect(self._stop_worker.deleteLater)
        self._stop_worker.error.connect(self._stop_worker.deleteLater)
        self._stop_worker.start()

    def stop_tracking(self) -> None:
        """
        Stop active tracking, call stop API on the backend,
        and clear session states on success.
        """
        if not self.is_tracking_active():
            return
        if self._is_stopping:
            return  # Prevent duplicate stop requests

        self._is_stopping = True
        self.status_message.emit("Stopping timer...")

        session = self._active_session
        entry_id = session["entry_id"]
        task_id = session["task_id"]
        elapsed = self.get_elapsed_seconds()

        # Stop local timer tick loop instantly
        self._timer.stop()

        # Stop sub-trackers
        for tracker in self._trackers:
            try:
                tracker.stop_tracker()
            except Exception as e:
                logger.error(f"Error stopping sub-tracker: {e}", exc_info=True)

        self._stop_worker = StopTimeEntryWorker(self.time_entry_service, entry_id, self.local_cache)

        def on_stop_success(result: dict) -> None:
            self._is_stopping = False

            # Add elapsed time to local cache database for reports/history
            if self.local_cache and elapsed > 0:
                try:
                    today_str = datetime.now().date().isoformat()
                    self.local_cache.add_elapsed_to_cached_time_entry(today_str, task_id, elapsed)
                except Exception as e:
                    logger.error(f"Error saving elapsed duration: {e}")

            # Clear running timer state in local cache
            if self.local_cache:
                self.local_cache.clear_app_state("timer_state")

            self._active_session = None
            self._start_monotonic = None
            self._elapsed_offset = 0

            self.tracking_stopped.emit(result)
            self.status_message.emit("Timer stopped")
            self._stop_worker = None

        def on_stop_error(msg: str) -> None:
            self._is_stopping = False
            # Resume local tick loop to keep UI consistent with backend failure
            self._timer.start(1000)
            self.error_occurred.emit(msg)
            self.status_message.emit("Failed to stop timer")
            self._stop_worker = None

        self._stop_worker.finished.connect(on_stop_success)
        self._stop_worker.error.connect(on_stop_error)
        self._stop_worker.finished.connect(self._stop_worker.deleteLater)
        self._stop_worker.error.connect(self._stop_worker.deleteLater)
        self._stop_worker.start()

    def restore_session(self, project_id: Optional[int], task_id: int, entry_id: int, elapsed_seconds: int, task_name: Optional[str] = None) -> None:
        """Restore active tracking session (e.g. on application launch)."""
        self._active_session = {
            "project_id": project_id,
            "task_id": task_id,
            "task_name": task_name,
            "entry_id": entry_id,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "elapsed": elapsed_seconds
        }
        self._start_monotonic = time.monotonic()
        self._elapsed_offset = elapsed_seconds
        self._timer.start(1000)

        # Notify sub-trackers of restored session
        for tracker in self._trackers:
            try:
                tracker.start_tracker(self._active_session)
            except Exception as e:
                logger.error(f"Error starting sub-tracker on restore: {e}", exc_info=True)

        self.tracking_started.emit(self._active_session)

    def _on_tick(self) -> None:
        """Tick event triggered every second while timer is running."""
        self.tick.emit(self.get_elapsed_seconds())
        # Periodically persist timer state (e.g., in case of crash)
        self._persist_timer_state()

    def _persist_timer_state(self) -> None:
        if not self.local_cache or not self._active_session:
            return
        try:
            state = {
                "running_task_id": self._active_session["task_id"],
                "running_task_name": self._active_session.get("task_name"),
                "running_entry_id": self._active_session["entry_id"],
                "running_elapsed_seconds": self.get_elapsed_seconds(),
            }
            self.local_cache.save_app_state("timer_state", state)
        except Exception:
            pass
