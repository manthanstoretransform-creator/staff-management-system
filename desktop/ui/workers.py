"""
QThread background workers — all API calls without blocking the UI thread.
"""
from typing import Optional
from PySide6.QtCore import QThread, Signal

from app.auth.service import AuthService
from app.projects.service import ProjectService
from app.tasks.service import TaskService
from app.time_entries.service import TimeEntryService
from app.api.client import ApiClient


class LoginWorker(QThread):
    """Authenticate user credentials without blocking the UI thread."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, auth_service: AuthService, username: str, password: str) -> None:
        super().__init__()
        self.auth_service = auth_service
        self.username = username
        self.password = password

    def run(self) -> None:
        try:
            user_data = self.auth_service.login(self.username, self.password)
            self.finished.emit(user_data)
        except Exception as e:
            self.error.emit(str(e))


class LoadProjectsWorker(QThread):
    """Fetch user projects from backend without blocking UI."""
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, project_service: ProjectService) -> None:
        super().__init__()
        self.project_service = project_service

    def run(self) -> None:
        try:
            projects = self.project_service.get_projects()
            self.finished.emit(projects)
        except Exception as e:
            self.error.emit(str(e))


class LoadTasksWorker(QThread):
    """Fetch tasks for a project without blocking UI."""
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, task_service: TaskService, project_id: int) -> None:
        super().__init__()
        self.task_service = task_service
        self.project_id = project_id

    def run(self) -> None:
        try:
            tasks = self.task_service.get_tasks_for_project(self.project_id)
            self.finished.emit(tasks)
        except Exception as e:
            self.error.emit(str(e))


class StartTimeEntryWorker(QThread):
    """Start a time entry on the backend without blocking UI."""
    finished = Signal(int)
    error = Signal(str)

    def __init__(self, time_entry_service: TimeEntryService, project_id: int, task_id: int) -> None:
        super().__init__()
        self.time_entry_service = time_entry_service
        self.project_id = project_id
        self.task_id = task_id

    def run(self) -> None:
        try:
            entry_id = self.time_entry_service.start_time_entry(self.project_id, self.task_id)
            self.finished.emit(entry_id)
        except Exception as e:
            self.error.emit(str(e))


class StopTimeEntryWorker(QThread):
    """Stop an active time entry on the backend without blocking UI."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, time_entry_service: TimeEntryService, entry_id: int, local_cache = None) -> None:
        super().__init__()
        self.time_entry_service = time_entry_service
        self.entry_id = entry_id
        self.local_cache = local_cache

    def run(self) -> None:
        try:
            # Sync final app usage segments for this time entry before stopping it
            if self.local_cache:
                try:
                    pending = self.local_cache.get_pending_app_usage()
                    # Filter for this specific time entry
                    records = [r for r in pending if r["time_entry_id"] == self.entry_id]
                    if records:
                        record_ids = [r["id"] for r in records]
                        self.local_cache.mark_app_usage_processing(record_ids)
                        
                        payload = {
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
                        self.time_entry_service.batch_sync_app_usage(self.entry_id, payload)
                        self.local_cache.complete_app_usage(record_ids)
                except Exception as e:
                    # If sync fails (e.g. offline), we release the records back to pending
                    # and proceed to try and stop the time entry.
                    if records:
                        self.local_cache.fail_app_usage(record_ids, str(e))

            result = self.time_entry_service.stop_time_entry(self.entry_id)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class LoadActiveTimerWorker(QThread):
    """
    Check backend for an active (running) time entry for the current user.
    Uses GET /time-entries?status=running&limit=1.
    Emits finished(dict) — the active entry dict, or {} if none exists.
    """
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, api_client: ApiClient) -> None:
        super().__init__()
        self.api_client = api_client

    def run(self) -> None:
        try:
            response = self.api_client.get(
                "/time-entries",
                params={"status": "running", "limit": 1}
            )
            entries = response.json()
            if isinstance(entries, list) and entries:
                # Extra safety: confirm end_time is None (truly active)
                active = next(
                    (e for e in entries if e.get("end_time") is None),
                    None
                )
                self.finished.emit(active if active else {})
            else:
                self.finished.emit({})
        except Exception as e:
            # Fail silently — not having an active timer is fine
            self.finished.emit({})


class LoadTodayTimeEntriesWorker(QThread):
    """
    Fetch time entries for a specific date to calculate Total Time Today.
    Uses GET /time-entries with the specified date range.
    """
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, api_client: ApiClient, target_date = None) -> None:
        super().__init__()
        self.api_client = api_client
        from datetime import date
        self.target_date = target_date or date.today()

    def run(self) -> None:
        try:
            from datetime import datetime
            today = self.target_date
            start_str = datetime(today.year, today.month, today.day, 0, 0, 0).isoformat()
            end_str = datetime(today.year, today.month, today.day, 23, 59, 59).isoformat()
            response = self.api_client.get(
                "/time-entries",
                params={"start_date": start_str, "end_date": end_str, "limit": 1000}
            )
            entries = response.json()
            if not isinstance(entries, list):
                entries = []
            self.finished.emit(entries)
        except Exception as e:
            self.error.emit(str(e))


class LoadScreenshotsWorker(QThread):
    """Fetch recent screenshots from backend."""
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, api_client: ApiClient) -> None:
        super().__init__()
        self.api_client = api_client

    def run(self) -> None:
        try:
            response = self.api_client.get(
                "/time-entry-screenshots",
                params={"limit": 12}
            )
            screenshots = response.json()
            if not isinstance(screenshots, list):
                screenshots = []
            self.finished.emit(screenshots)
        except Exception as e:
            self.error.emit(str(e))


class CreateTaskWorker(QThread):
    """Create a task via TaskService in background."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, task_service: TaskService, project_id: int, task_name: str, assignee_id: int) -> None:
        super().__init__()
        self.task_service = task_service
        self.project_id = project_id
        self.task_name = task_name
        self.assignee_id = assignee_id

    def run(self) -> None:
        try:
            task = self.task_service.create_task(
                self.project_id, self.task_name, self.assignee_id
            )
            self.finished.emit(task)
        except Exception as e:
            self.error.emit(str(e))


class UpdateTaskWorker(QThread):
    """Update a task via TaskService in background."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, task_service: TaskService, project_id: int, task_id: int, task_name: str, status_id: int) -> None:
        super().__init__()
        self.task_service = task_service
        self.project_id = project_id
        self.task_id = task_id
        self.task_name = task_name
        self.status_id = status_id

    def run(self) -> None:
        try:
            task = self.task_service.update_task(
                self.project_id, self.task_id, self.task_name, self.status_id
            )
            self.finished.emit(task)
        except Exception as e:
            self.error.emit(str(e))


class LoadTaskStatusesWorker(QThread):
    """Fetch task statuses from backend without blocking UI."""
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, task_service: TaskService) -> None:
        super().__init__()
        self.task_service = task_service

    def run(self) -> None:
        try:
            statuses = self.task_service.get_task_statuses()
            self.finished.emit(statuses)
        except Exception as e:
            self.error.emit(str(e))


class DeleteTaskWorker(QThread):
    """Delete a task via TaskService in background."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, task_service: TaskService, project_id: int, task_id: int) -> None:
        super().__init__()
        self.task_service = task_service
        self.project_id = project_id
        self.task_id = task_id

    def run(self) -> None:
        try:
            result = self.task_service.delete_task(self.project_id, self.task_id)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class VerifySessionWorker(QThread):
    """Verify stored token by calling /auth/me in background on startup."""
    finished = Signal(dict)
    error = Signal(Exception)

    def __init__(self, api_client: ApiClient, token: str) -> None:
        super().__init__()
        self.api_client = api_client
        self.token = token

    def run(self) -> None:
        self.api_client.access_token = self.token
        try:
            response = self.api_client.get("/auth/me")
            user_data = response.json()
            self.finished.emit(user_data)
        except Exception as e:
            self.error.emit(e)
