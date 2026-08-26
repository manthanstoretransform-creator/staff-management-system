"""
sync_queue — Background sync queue that processes pending API operations.

Runs as a single QThread that continuously polls the local SQLite cache
for pending actions and processes them in priority order. Implements:
  - Exponential backoff retry
  - Idempotency (duplicate detection)
  - Pause/resume on network status changes
  - Clean shutdown with state persistence
  - Qt Signals for UI feedback on success/failure

Priority levels (lower = higher priority):
  1 = stop_timer
  2 = start_timer
  3 = switch_timer (atomic stop+start)
  5 = create_task, update_task, delete_task
  8 = refresh_data
"""
import time
import traceback
from typing import Any, Dict, Optional

from PySide6.QtCore import QThread, Signal, QMutex, QWaitCondition

from sync.local_cache import LocalCache
from app.api.exceptions import ApiError, ApiHttpError, ApiConnectionError, ApiTimeoutError
from app.time_entries.service import TimeEntryService
from app.tasks.service import TaskService


class SyncQueue(QThread):
    """
    Background worker thread that processes the persistent action queue.

    Signals:
        action_completed(action_id, action_type, result_dict)
        action_failed(action_id, action_type, error_str, will_retry)
        auth_required()  — emitted on 401, queue pauses
        queue_empty()    — emitted when all pending actions are processed
        sync_status(pending_count) — emitted periodically with queue depth
    """
    action_completed = Signal(str, str, dict)    # action_id, action_type, result
    action_failed = Signal(str, str, str, bool)  # action_id, action_type, error, will_retry
    auth_required = Signal()
    queue_empty = Signal()
    sync_status = Signal(int)  # pending_count

    # Interval between queue polls when idle (ms)
    POLL_INTERVAL_MS = 500
    # Interval between queue polls when processing (ms)
    BUSY_INTERVAL_MS = 50

    def __init__(
        self,
        cache: LocalCache,
        time_entry_service: TimeEntryService,
        task_service: TaskService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._cache = cache
        self._time_entry_service = time_entry_service
        self._task_service = task_service

        self._running = True
        self._paused = False
        self._mutex = QMutex()
        self._condition = QWaitCondition()

    def stop(self) -> None:
        """Signal the queue to stop processing and exit."""
        self._running = False
        self._condition.wakeAll()

    def pause(self) -> None:
        """Pause queue processing (e.g., when offline)."""
        self._paused = True

    def resume(self) -> None:
        """Resume queue processing (e.g., when back online)."""
        self._paused = False
        self._condition.wakeAll()

    def wake(self) -> None:
        """Wake the queue to process newly enqueued actions immediately."""
        self._condition.wakeAll()

    def run(self) -> None:
        """Main queue processing loop."""
        # On startup, reset any actions that were interrupted mid-processing
        self._cache.reset_processing_actions()
        self._cache.reset_processing_app_usage()
        self._cache.clear_stale_actions()

        while self._running:
            if self._paused:
                # Sleep while paused, wake on resume() or stop()
                self._mutex.lock()
                self._condition.wait(self._mutex, 2000)
                self._mutex.unlock()
                continue

            action = self._cache.get_next_pending_action()

            if action is None:
                # Synchronize pending app usage records
                self._sync_app_usage()

                # Queue is empty, emit status and sleep
                pending = self._cache.get_pending_count()
                self.sync_status.emit(pending)
                if pending == 0:
                    self.queue_empty.emit()

                self._mutex.lock()
                self._condition.wait(self._mutex, self.POLL_INTERVAL_MS)
                self._mutex.unlock()
                continue

            # Process the action
            self._process_action(action)

            # Brief pause between actions to avoid hammering the API
            self._mutex.lock()
            self._condition.wait(self._mutex, self.BUSY_INTERVAL_MS)
            self._mutex.unlock()

    def _process_action(self, action: Dict[str, Any]) -> None:
        """Route an action to the appropriate handler."""
        action_id = action["id"]
        action_type = action["action_type"]
        payload = action["payload"]

        try:
            result = {}

            if action_type == "start_timer":
                result = self._handle_start_timer(payload)
            elif action_type == "stop_timer":
                result = self._handle_stop_timer(payload)
            elif action_type == "switch_timer":
                result = self._handle_switch_timer(payload)
            elif action_type == "create_task":
                result = self._handle_create_task(payload)
            elif action_type == "update_task":
                result = self._handle_update_task(payload)
            elif action_type == "delete_task":
                result = self._handle_delete_task(payload)
            else:
                # Unknown action type — mark as completed to avoid infinite loop
                result = {"warning": f"Unknown action type: {action_type}"}

            # Success — remove from queue
            self._cache.complete_action(action_id)
            self.action_completed.emit(action_id, action_type, result)

        except ApiError as e:
            error_msg = str(e)
            status_code = getattr(e, "status_code", None)

            if status_code == 401 or "session expired" in error_msg.lower():
                # Auth expired — pause queue, signal re-login
                self._cache.fail_action(action_id, error_msg, max_retries=0)
                self._paused = True
                self.auth_required.emit()
                self.action_failed.emit(action_id, action_type, "Session expired", False)
            elif status_code == 409 or "already has an active timer" in error_msg.lower() or "already stopped" in error_msg.lower():
                # Conflict — mark completed since the state is already reconciled
                self._cache.complete_action(action_id)
                self.action_completed.emit(action_id, action_type, {"conflict": True, "status_code": 409})
            elif status_code == 404 or "not found" in error_msg.lower():
                # Resource not found — mark completed to clean up queue
                self._cache.complete_action(action_id)
                self.action_failed.emit(action_id, action_type, error_msg, False)
            else:
                will_retry = self._cache.fail_action(action_id, error_msg)
                self.action_failed.emit(action_id, action_type, error_msg, will_retry)

        except Exception as e:
            # Unexpected error — retry with backoff
            error_msg = f"{type(e).__name__}: {str(e)}"
            will_retry = self._cache.fail_action(action_id, error_msg)
            self.action_failed.emit(action_id, action_type, error_msg, will_retry)

    # ── Action Handlers ───────────────────────────────────────────────────────

    def _handle_start_timer(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Start a time entry on the backend."""
        project_id = payload["project_id"]
        task_id = payload["task_id"]
        entry_id = self._time_entry_service.start_time_entry(project_id, task_id)
        return {"entry_id": entry_id, "project_id": project_id, "task_id": task_id}

    def _handle_stop_timer(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Stop an active time entry on the backend."""
        entry_id = payload["entry_id"]
        task_id = payload.get("task_id")
        result = self._time_entry_service.stop_time_entry(entry_id)
        if isinstance(result, dict) and task_id:
            result["task_id"] = task_id
        return result

    def _handle_switch_timer(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Atomic stop + start for timer switching."""
        old_entry_id = payload["old_entry_id"]
        old_task_id = payload.get("old_task_id")
        new_project_id = payload["new_project_id"]
        new_task_id = payload["new_task_id"]

        # Step 1: Stop old timer
        stop_result = {}
        if old_entry_id and old_entry_id > 0:
            try:
                stop_result = self._time_entry_service.stop_time_entry(old_entry_id)
            except Exception as e:
                # If old entry was already stopped or not found, proceed to start new timer
                stop_result = {"warning": str(e)}

        # Step 2: Start new timer
        new_entry_id = self._time_entry_service.start_time_entry(new_project_id, new_task_id)

        return {
            "stop_result": stop_result,
            "old_task_id": old_task_id,
            "new_entry_id": new_entry_id,
            "new_project_id": new_project_id,
            "new_task_id": new_task_id,
        }

    def _handle_create_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a task on the backend."""
        result = self._task_service.create_task(
            payload["project_id"],
            payload["task_name"],
            payload.get("assignee_id") or 1,
            payload.get("status_id") or 1,
        )
        return result

    def _handle_update_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update a task on the backend."""
        result = self._task_service.update_task(
            payload["project_id"],
            payload["task_id"],
            payload["task_name"],
            payload.get("status_id") or 1,
            payload.get("assignee_id"),
        )
        return result

    def _handle_delete_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Delete (archive) a task on the backend."""
        result = self._task_service.delete_task(
            payload["project_id"],
            payload["task_id"],
        )
        return result

    def _sync_app_usage(self) -> None:
        """Fetch pending app usage records, group by time_entry_id, batch sync to backend."""
        try:
            pending_records = self._cache.get_pending_app_usage()
            if not pending_records:
                return

            # Group by time_entry_id
            grouped = {}
            for r in pending_records:
                entry_id = r["time_entry_id"]
                grouped.setdefault(entry_id, []).append(r)

            for entry_id, records in grouped.items():
                record_ids = [r["id"] for r in records]
                self._cache.mark_app_usage_processing(record_ids)
                
                # Format payload for API
                batch_payload = {
                    "records": [
                        {
                            "application_name": r["application_name"],
                            "window_title": r["window_title"],
                            "duration_seconds": r["duration_seconds"],
                            "recorded_at": r["recorded_at"]
                        }
                        for r in records
                    ]
                }

                try:
                    # Use extended time entry service to batch sync
                    self._time_entry_service.batch_sync_app_usage(entry_id, batch_payload)
                    # Success - complete records
                    self._cache.complete_app_usage(record_ids)
                except Exception as e:
                    # Failure - retry with backoff
                    error_msg = str(e)
                    self._cache.fail_app_usage(record_ids, error_msg)
                    # Emit fail action signal if useful
                    self.action_failed.emit("", "batch_app_usage", error_msg, True)
        except Exception:
            # Shield main sync loop from any sqlite/sync processing errors
            pass
