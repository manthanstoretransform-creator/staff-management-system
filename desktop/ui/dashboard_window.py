"""
Dashboard window — main application shell.
Assembles sidebar + top bar + main content (task table + screenshots).
Preserves all existing service layer connections.
"""
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, Signal, QTimer
from shiboken6 import isValid
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QScrollArea,
    QFrame, QLabel, QSizePolicy, QApplication
)

from app.auth.session import SessionManager
from app.projects.service import ProjectService
from app.tasks.service import TaskService
from app.time_entries.service import TimeEntryService
from app.api.client import ApiClient
from app.timer.engine import TimerState

from ui.sidebar import SidebarWidget
from ui.topbar import TopBar
from ui.task_table import TaskSection
from ui.activity_section import ActivitySection
from ui.workers import (
    LoadProjectsWorker, LoadTasksWorker, LoadTodayTimeEntriesWorker,
    LoadTaskStatusesWorker
)
from ui.styles import (
    CONTENT_BG, TEXT_PRIMARY, TEXT_MUTED, TEXT_SECONDARY,
    BORDER_LIGHT, CARD_BG, SUCCESS, ERROR, WARNING, PROJECT_COLORS
)


class StatusBar(QFrame):
    """Thin status bar at the very bottom of the dashboard."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(26)
        self.setStyleSheet(f"""
            QFrame {{
                background: #F1F5F9;
                border-top: 1px solid {BORDER_LIGHT};
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        self._msg = QLabel("Ready", self)
        self._msg.setFont(QFont("Segoe UI", 10))
        self._msg.setStyleSheet(f"color: {TEXT_MUTED};")
        layout.addWidget(self._msg)
        layout.addStretch()

        self._timer_status = QLabel("", self)
        self._timer_status.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self._timer_status.setStyleSheet(f"color: {TEXT_MUTED};")
        layout.addWidget(self._timer_status)

    def set_message(self, msg: str, color: str = None) -> None:
        self._msg.setText(msg)
        if color:
            self._msg.setStyleSheet(f"color: {color};")
        else:
            self._msg.setStyleSheet(f"color: {TEXT_MUTED};")

    def set_timer_info(self, info: str) -> None:
        self._timer_status.setText(info)


class DashboardWindow(QWidget):
    """
    Full-screen dashboard widget:
    ┌────────────┬────────────────────────────────────────────────┐
    │  Sidebar   │  TopBar                                        │
    │            ├────────────────────────────────────────────────┤
    │            │  Scrollable content:                           │
    │            │    TaskSection                                 │
    │            │    ScreenshotSection                           │
    └────────────┴────────────────────────────────────────────────┘
    """
    logout_requested = Signal()
    unauthorized_error = Signal()

    def __init__(
        self,
        session_manager: SessionManager,
        project_service: ProjectService,
        task_service: TaskService,
        time_entry_service: TimeEntryService,
        api_client: ApiClient,
        local_cache = None,
        sync_queue = None,
        network_monitor = None,
        tracking_manager = None,
        notification_manager = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._tracking_manager = tracking_manager
        self._notification_manager = notification_manager
        self.session_manager = session_manager
        self.project_service = project_service
        self.task_service = task_service
        self.time_entry_service = time_entry_service
        self.api_client = api_client
        self._local_cache = local_cache
        self._sync_queue = sync_queue
        self._network_monitor = network_monitor

        self._projects: List[Dict[str, Any]] = []
        self._current_project: Optional[Dict[str, Any]] = None
        self._current_project_color = "#3B82F6"
        self._is_timer_active = False
        self._was_online = None

        # Workers
        self._projects_worker: Optional[LoadProjectsWorker] = None
        self._tasks_worker: Optional[LoadTasksWorker] = None
        self._today_worker: Optional[LoadTodayTimeEntriesWorker] = None
        self._statuses_worker: Optional[LoadTaskStatusesWorker] = None
        self._running_workers = set()
        self._refresh_timer: Optional[QTimer] = None

        self._build_ui()

        # Connect SyncQueue and NetworkMonitor
        if self._sync_queue:
            self._task_section.set_sync_queue(self._sync_queue)
            self._sync_queue.sync_status.connect(self._on_sync_status)
            self._sync_queue.queue_empty.connect(self._on_queue_empty)
            self._sync_queue.action_failed.connect(self._on_sync_action_failed)
        if self._local_cache:
            self._task_section.set_local_cache(self._local_cache)
        if self._network_monitor:
            self._network_monitor.status_changed.connect(self._on_network_status_changed)
            self._network_monitor.latency_measured.connect(self._topbar.set_latency)
            self._topbar.set_connected(self._network_monitor.is_online)

        self._task_section.refresh_requested.connect(self.refresh_data)

        # Periodic refresh timer (60 seconds)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh_data)

    def _start_worker(self, worker) -> None:
        self._running_workers.add(worker)
        worker.finished.connect(lambda: self._running_workers.discard(worker))
        worker.error.connect(lambda: self._running_workers.discard(worker))
        worker.start()

    def _safely_stop_worker(self, attr_name: str) -> None:
        """Safely stop a running QThread worker attribute by disconnecting slots, avoiding unsafe terminate()."""
        worker = getattr(self, attr_name, None)
        if worker is not None:
            try:
                # Disconnect signals from UI slots so it doesn't trigger UI updates after being discarded
                worker.finished.disconnect()
            except Exception:
                pass
            try:
                worker.error.disconnect()
            except Exception:
                pass
            # Ensure it still cleans up when finished
            try:
                worker.finished.connect(worker.deleteLater)
                worker.error.connect(worker.deleteLater)
            except Exception:
                pass
            setattr(self, attr_name, None)

    def _build_ui(self) -> None:
        self.setStyleSheet(f"QWidget {{ background: {CONTENT_BG}; }}")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Horizontal split: Sidebar | Content ───────────────────
        h_split = QWidget(self)
        h_layout = QHBoxLayout(h_split)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        # ── Sidebar ────────────────────────────────────────────────
        self._sidebar = SidebarWidget(self)
        self._sidebar.project_selected.connect(self._on_project_selected)
        self._sidebar.logout_requested.connect(self._handle_logout)
        self._sidebar.collapse_toggled.connect(self._on_sidebar_toggled)
        h_layout.addWidget(self._sidebar)

        # ── Right column: TopBar + content ────────────────────────
        right_col = QWidget(h_split)
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Top bar
        self._topbar = TopBar(right_col)
        self._topbar.date_changed.connect(self._on_date_changed)
        right_layout.addWidget(self._topbar)

        # Scrollable main content
        self._scroll_area = QScrollArea(right_col)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setStyleSheet(f"QScrollArea {{ background: {CONTENT_BG}; border: none; }}")

        scroll_content = QWidget()
        scroll_content.setStyleSheet(f"background: {CONTENT_BG};")
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(20, 16, 20, 20)
        content_layout.setSpacing(16)

        # Task section
        self._task_section = TaskSection(
            time_entry_service=self.time_entry_service,
            task_service=self.task_service,
            tracking_manager=self._tracking_manager,
            parent=scroll_content
        )
        self._task_section.timer_state_changed.connect(self._on_timer_state_changed)
        self._task_section.error_occurred.connect(self._on_error)
        self._task_section.active_timer_conflict.connect(self._reconcile_active_timer)
        self._task_section.task_action_succeeded.connect(self._on_task_action_succeeded)
        content_layout.addWidget(self._task_section, 4)

        # Activity section
        self._activity_section = ActivitySection(self.api_client, scroll_content)
        content_layout.addWidget(self._activity_section, 6)

        self._scroll_area.setWidget(scroll_content)
        right_layout.addWidget(self._scroll_area, 1)

        h_layout.addWidget(right_col, 1)
        root_layout.addWidget(h_split, 1)

        # ── Status bar ─────────────────────────────────────────────
        self._status_bar = StatusBar(self)
        root_layout.addWidget(self._status_bar)

    # ── Public API (called by MainWindow) ──────────────────────────────────────

    def on_login(self, user_data: dict) -> None:
        """Called after successful login to initialize the dashboard."""
        self._sidebar.set_user(user_data)
        self._task_section.set_user_role(user_data.get("role_name"))
        self._task_section.set_user_id(user_data.get("id"))
        
        if self._refresh_timer:
            self._refresh_timer.start(60 * 1000)
            
        self._load_task_statuses()
        
        # Load projects from cache first
        loaded_from_cache = False
        if self._local_cache:
            cached_projects = self._local_cache.get_cached_projects()
            if cached_projects:
                self._projects = cached_projects
                self._sidebar.set_projects(cached_projects)
                self._status_bar.set_message("Loaded projects from cache.")
                self._apply_active_timer_if_ready()
                loaded_from_cache = True
            
            # Check for crash-recovered active timer
            timer_state = self._local_cache.load_app_state("timer_state")
            if timer_state:
                task_id = timer_state.get("running_task_id")
                entry_id = timer_state.get("running_entry_id")
                elapsed = timer_state.get("running_elapsed_seconds", 0)
                if task_id:
                    self._is_timer_active = True
                    self._sidebar.set_timer_active(True)
                    if self._tracking_manager:
                        self._tracking_manager.restore_session(None, task_id, entry_id or -1, elapsed)
                    else:
                        self._task_section.sync_active_timer(task_id, entry_id or -1, elapsed)

        if not loaded_from_cache:
            self._status_bar.set_message("Loading projects...")

        self.load_projects()
        self._check_active_timer()
        self._load_today_time()
        self._activity_section.refresh()

    def load_projects(self) -> None:
        """Trigger background load of projects."""
        worker = getattr(self, "_projects_worker", None)
        if worker and isValid(worker) and worker.isRunning():
            return
        self._safely_stop_worker("_projects_worker")
        self._projects_worker = LoadProjectsWorker(self.project_service)
        self._projects_worker.finished.connect(self._on_projects_loaded)
        self._projects_worker.error.connect(self._on_projects_error)
        self._projects_worker.finished.connect(self._projects_worker.deleteLater)
        self._projects_worker.error.connect(self._projects_worker.deleteLater)
        self._start_worker(self._projects_worker)

    def _load_task_statuses(self) -> None:
        """Load task statuses from backend and cache them."""
        worker = getattr(self, "_statuses_worker", None)
        if worker and isValid(worker) and worker.isRunning():
            return
        self._safely_stop_worker("_statuses_worker")
        self._statuses_worker = LoadTaskStatusesWorker(self.task_service)
        def on_loaded(statuses):
            if self._local_cache:
                self._local_cache.cache_task_statuses(statuses)
        self._statuses_worker.finished.connect(on_loaded)
        self._statuses_worker.finished.connect(self._statuses_worker.deleteLater)
        self._statuses_worker.error.connect(self._statuses_worker.deleteLater)
        self._start_worker(self._statuses_worker)

    def refresh_data(self) -> None:
        """Fetch latest project/task data from backend and refresh cache/UI."""
        if not self._network_monitor or self._network_monitor.is_online:
            self.load_projects()
            self._load_task_statuses()
            if self._current_project:
                project_id = self._current_project.get("id")
                worker = getattr(self, "_tasks_worker", None)
                if worker and isValid(worker) and worker.isRunning() and getattr(worker, "project_id", None) == project_id:
                    pass
                else:
                    self._safely_stop_worker("_tasks_worker")
                    self._tasks_worker = LoadTasksWorker(self.task_service, project_id)
                    self._tasks_worker.finished.connect(self._on_tasks_loaded)
                    self._tasks_worker.error.connect(self._on_tasks_error)
                    self._tasks_worker.finished.connect(self._tasks_worker.deleteLater)
                    self._tasks_worker.error.connect(self._tasks_worker.deleteLater)
                    self._start_worker(self._tasks_worker)

    @property
    def is_timer_running(self) -> bool:
        """Return True if a task timer is actively running in the task section or window."""
        return getattr(self, "_is_timer_active", False) or (
            hasattr(self, "_task_section") and getattr(self._task_section, "_running_task_id", None) is not None
        )

    def get_running_entry_id(self) -> Optional[int]:
        """Return the active time entry ID if a timer is running."""
        if hasattr(self, "_task_section") and getattr(self._task_section, "_running_entry_id", None):
            return getattr(self._task_section, "_running_entry_id")
        return getattr(self, "_running_entry_id", None)

    def reset_state(self) -> None:
        """Clear all state when logging out."""
        self._projects = []
        self._current_project = None
        self._is_timer_active = False
        self._sidebar.set_projects([])
        self._task_section.clear()
        self._sidebar.set_timer_active(False)
        self._sidebar.set_total_seconds(0)
        self._status_bar.set_message("Ready")
        if self._refresh_timer:
            self._refresh_timer.stop()

    # ── Project loading ────────────────────────────────────────────────────────

    def _on_projects_loaded(self, projects: list) -> None:
        self._projects = projects
        self._sidebar.set_projects(projects)
        if self._local_cache:
            self._local_cache.cache_projects(projects)
        if projects:
            self._status_bar.set_message(f"Loaded {len(projects)} projects.")
            self._apply_active_timer_if_ready()
        else:
            self._status_bar.set_message("No projects found.", TEXT_MUTED)
            self._task_section.clear()
        self._topbar.set_connected(True)

    def _on_projects_error(self, error: str) -> None:
        # If we already have projects from cache, keep displaying them gracefully
        if self._projects:
            self._topbar.set_connected(False)
            self._status_bar.set_message("Working offline — displaying cached projects.", WARNING)
            return
        self._status_bar.set_message(f"Failed to load projects: {error}", ERROR)
        if "session expired" in error.lower():
            self.unauthorized_error.emit()

    # ── Project selection ──────────────────────────────────────────────────────

    def _on_project_selected(self, project: Dict[str, Any]) -> None:
        self._current_project = project
        project_id = project.get("id")
        project_name = project.get("project_name", "Project")

        # Determine color
        idx = next(
            (i for i, p in enumerate(self._projects) if p.get("id") == project_id), 0
        )
        self._current_project_color = PROJECT_COLORS[idx % len(PROJECT_COLORS)]

        # Highlight in sidebar
        self._sidebar.select_project(project_id)

        # Load tasks from cache first
        loaded_from_cache = False
        if self._local_cache:
            cached_tasks = self._local_cache.get_cached_tasks(project_id)
            if cached_tasks is not None:
                # Inject today's tracked seconds into cached tasks before displaying them
                if hasattr(self, "_today_time_entries") and self._today_time_entries:
                    task_time_map = {}
                    for entry in self._today_time_entries:
                        tid = entry.get("task_id")
                        if tid:
                            if entry.get("status") in ("stopped", "completed") or entry.get("end_time") is not None:
                                task_time_map[tid] = task_time_map.get(tid, 0) + entry.get("total_seconds", 0)
                    for t in cached_tasks:
                        tid = t.get("id")
                        t["time_tracked_seconds"] = task_time_map.get(tid, 0)

                self._task_section.set_tasks(
                    cached_tasks, self._current_project, self._current_project_color
                )
                self._status_bar.set_message(f"Loaded tasks from cache.")
                loaded_from_cache = True

        if not loaded_from_cache:
            self._task_section.set_loading(project_name)

        # Background load/refresh
        worker = getattr(self, "_tasks_worker", None)
        if worker and isValid(worker) and worker.isRunning() and getattr(worker, "project_id", None) == project_id:
            return
        self._safely_stop_worker("_tasks_worker")
        self._tasks_worker = LoadTasksWorker(self.task_service, project_id)
        self._tasks_worker.finished.connect(self._on_tasks_loaded)
        self._tasks_worker.error.connect(self._on_tasks_error)
        self._tasks_worker.finished.connect(self._tasks_worker.deleteLater)
        self._tasks_worker.error.connect(self._tasks_worker.deleteLater)
        self._start_worker(self._tasks_worker)

    def _on_tasks_loaded(self, tasks: list) -> None:
        if self._current_project:
            # Inject today's tracked seconds into tasks before displaying them
            if hasattr(self, "_today_time_entries") and self._today_time_entries:
                task_time_map = {}
                for entry in self._today_time_entries:
                    tid = entry.get("task_id")
                    if tid:
                        if entry.get("status") in ("stopped", "completed") or entry.get("end_time") is not None:
                            task_time_map[tid] = task_time_map.get(tid, 0) + entry.get("total_seconds", 0)
                for t in tasks:
                    tid = t.get("id")
                    t["time_tracked_seconds"] = task_time_map.get(tid, 0)

            self._task_section.set_tasks(
                tasks, self._current_project, self._current_project_color
            )
            self._status_bar.set_message(f"{len(tasks)} tasks loaded.")
            if self._local_cache:
                self._local_cache.cache_tasks(self._current_project.get("id"), tasks)
        self._topbar.set_connected(True)

    def _on_tasks_error(self, error: str) -> None:
        # If we already loaded tasks from cache for this project, keep displaying them gracefully
        if getattr(self._task_section, "_has_loaded_tasks", False):
            self._topbar.set_connected(False)
            self._status_bar.set_message("Working offline — displaying cached tasks.", WARNING)
            return
        self._task_section.set_error(error)
        self._status_bar.set_message(f"Failed to load tasks: {error}", ERROR)
        if "session expired" in error.lower():
            self.unauthorized_error.emit()

    # ── Today's time ───────────────────────────────────────────────────────────

    def _load_today_time(self) -> None:
        # Load from cache first
        if self._local_cache:
            from datetime import date
            today_str = date.today().isoformat()
            cached_entries = self._local_cache.get_cached_time_entries(today_str)
            if cached_entries:
                self._on_today_time_loaded(cached_entries, update_cache=False, target_date=date.today())

        self._safely_stop_worker("_today_worker")
        self._today_worker = LoadTodayTimeEntriesWorker(self.api_client)
        self._today_worker.finished.connect(lambda entries: self._on_today_time_loaded(entries, update_cache=True, target_date=date.today()))
        self._today_worker.error.connect(lambda _: None)  # Silent fail
        self._today_worker.finished.connect(self._today_worker.deleteLater)
        self._today_worker.error.connect(self._today_worker.deleteLater)
        self._start_worker(self._today_worker)

    def _on_today_time_loaded(self, entries: list, update_cache: bool = True, target_date = None) -> None:
        """Sum total_seconds from all today's completed entries (including active elapsed)."""
        from datetime import date
        t_date = target_date or date.today()
        total = sum(
            e.get("total_seconds", 0)
            for e in entries
            if e.get("status") in ("stopped", "completed") or e.get("end_time") is not None
        )
        active_elapsed = 0
        if t_date == date.today():
            if self._is_timer_active and hasattr(self._task_section, "_running_elapsed_seconds"):
                active_elapsed = self._task_section._running_elapsed_seconds
        self._sidebar.set_total_seconds(total + active_elapsed)

        self._today_time_entries = entries

        if update_cache and self._local_cache:
            date_str = t_date.isoformat()
            self._local_cache.cache_time_entries(date_str, entries)

        self._update_task_tracked_times()

    def _update_task_tracked_times(self) -> None:
        if not hasattr(self, "_today_time_entries") or not self._today_time_entries:
            return
        task_time_map = {}
        for entry in self._today_time_entries:
            tid = entry.get("task_id")
            if tid:
                if entry.get("status") in ("stopped", "completed") or entry.get("end_time") is not None:
                    task_time_map[tid] = task_time_map.get(tid, 0) + entry.get("total_seconds", 0)
        if hasattr(self, "_task_section") and self._task_section:
            self._task_section.update_tasks_tracked_times(task_time_map)

    # ── Timer state changes ────────────────────────────────────────────────────

    def _on_timer_state_changed(self, active: bool) -> None:
        self._is_timer_active = active
        self._sidebar.set_timer_active(active)
        if active:
            self._status_bar.set_timer_info("● Timer running")
            self._status_bar.set_message("Tracking time...")
        else:
            self._status_bar.set_timer_info("")
            self._status_bar.set_message("Timer stopped.")
            # Reload today's total after stopping
            QTimer.singleShot(500, self._load_today_time)

    def _on_error(self, msg: str) -> None:
        self._status_bar.set_message(f"Error: {msg}", ERROR)
        if "session expired" in msg.lower():
            self.unauthorized_error.emit()

    # ── Sidebar collapse ───────────────────────────────────────────────────────

    def _on_sidebar_toggled(self, collapsed: bool) -> None:
        pass  # Width is handled by SidebarWidget itself

    # ── Date navigation & Task actions ─────────────────────────────────────────

    def _on_date_changed(self, target_date) -> None:
        self._status_bar.set_message(f"Loading data for {target_date}...")
        
        # Load from cache first for instant response
        if self._local_cache:
            date_str = target_date.isoformat()
            cached_entries = self._local_cache.get_cached_time_entries(date_str)
            if cached_entries:
                self._on_today_time_loaded(cached_entries, update_cache=False, target_date=target_date)

        self._safely_stop_worker("_today_worker")
        self._today_worker = LoadTodayTimeEntriesWorker(self.api_client, target_date)
        self._today_worker.finished.connect(lambda entries: self._on_today_time_loaded(entries, update_cache=True, target_date=target_date))
        self._today_worker.error.connect(lambda _: None)
        self._today_worker.finished.connect(self._today_worker.deleteLater)
        self._today_worker.error.connect(self._today_worker.deleteLater)
        self._start_worker(self._today_worker)

    def _on_network_status_changed(self, is_online: bool) -> None:
        self._topbar.set_connected(is_online)
        if is_online:
            self._status_bar.set_message("Online", SUCCESS)
            if self._sync_queue:
                self._sync_queue.resume()
            if not self._projects:
                self.load_projects()
            elif self._current_project:
                self._on_project_selected(self._current_project)
            
            # Show online notification on state transition
            if self._was_online is False:
                if self._notification_manager:
                    self._notification_manager.show_success("Back online. Syncing pending activity.")
                self.refresh_data()
        else:
            self._status_bar.set_message("Working offline — displaying cached data.", WARNING)
            if self._sync_queue:
                self._sync_queue.pause()
            
            # Show offline notification on state transition
            if self._was_online is True or self._was_online is None:
                if self._notification_manager:
                    self._notification_manager.show_warning("You are offline. Your activity will be saved locally and retried automatically.")

        self._was_online = is_online

    def _on_task_action_succeeded(self, message: str) -> None:
        self._status_bar.set_message(message, SUCCESS)
        if self._notification_manager:
            # Normalize message for concise notifications
            msg = message.replace("create_taskd", "created").replace("update_taskd", "updated").replace("delete_taskd", "deleted")
            msg = msg.replace("create taskd", "created").replace("update taskd", "updated").replace("delete taskd", "deleted")
            self._notification_manager.show_success(msg)


    def _on_sync_status(self, pending: int) -> None:
        self._topbar.set_sync_status(pending)
        if pending > 0:
            self._had_pending_sync = True

    def _on_queue_empty(self) -> None:
        if getattr(self, "_had_pending_sync", False):
            self._had_pending_sync = False
            if self._notification_manager:
                self._notification_manager.show_success("Pending activity synced successfully")
        if self._current_project:
            self._on_project_selected(self._current_project)
        self._load_today_time()

    def _on_sync_action_failed(self, action_id: str, action_type: str, error: str, will_retry: bool) -> None:
        if not will_retry and action_type in ("start_timer", "stop_timer", "switch_timer"):
            if self._notification_manager:
                self._notification_manager.show_error("Unable to sync activity. Your data is saved locally and will retry automatically.")

    # ── Logout ─────────────────────────────────────────────────────────────────

    def _handle_logout(self) -> None:
        self.reset_state()
        self.logout_requested.emit()

    # ── Timer running guard / Check Active Timer ────────────────────────────────
    
    def _check_active_timer(self) -> None:
        from ui.workers import LoadActiveTimerWorker
        self._safely_stop_worker("_active_worker")
        self._active_worker = LoadActiveTimerWorker(self.api_client)
        self._active_worker.finished.connect(self._on_active_timer_checked)
        self._active_worker.finished.connect(self._active_worker.deleteLater)
        self._active_worker.error.connect(self._active_worker.deleteLater)
        self._start_worker(self._active_worker)

    def _on_active_timer_checked(self, active_entry: dict) -> None:
        if not active_entry or "id" not in active_entry:
            return
        self._pending_active_timer = active_entry
        self._apply_active_timer_if_ready()

    def _apply_active_timer_if_ready(self) -> None:
        if not hasattr(self, "_pending_active_timer") or not self._pending_active_timer:
            return
        if not self._projects:
            return
            
        active_entry = self._pending_active_timer
        self._pending_active_timer = None # Consume
        
        project_id = active_entry.get("project_id")
        task_id = active_entry.get("task_id")
        entry_id = active_entry.get("id")
        start_time_str = active_entry.get("start_time")
        
        if not project_id or not task_id or not entry_id:
            return
            
        try:
            from datetime import datetime, timezone
            if start_time_str.endswith("Z"):
                start_time_str = start_time_str[:-1] + "+00:00"
            dt_start = datetime.fromisoformat(start_time_str)
            now = datetime.now(timezone.utc)
            elapsed = int((now - dt_start).total_seconds())
            if elapsed < 0:
                elapsed = 0
        except Exception:
            elapsed = 0

        task_data = active_entry.get("task")
        task_name = None
        if isinstance(task_data, dict):
            task_name = task_data.get("name") or task_data.get("task_name")

        self._is_timer_active = True
        if self._tracking_manager:
            self._tracking_manager.restore_session(project_id, task_id, entry_id, elapsed, task_name)
        else:
            self._task_section._running_task_id = task_id
            self._task_section._running_entry_id = entry_id
            self._task_section._running_elapsed_seconds = elapsed
            self._task_section._running_task_name = task_name
        
        self._sidebar.set_timer_active(True)
        
        # Select active project first so tasks load
        if self._current_project and self._current_project.get("id") == project_id:
            self._task_section.sync_active_timer(task_id, entry_id, elapsed)
        else:
            for project in self._projects:
                if project.get("id") == project_id:
                    self._on_project_selected(project)
                    break
        
        # Refresh today's total calculation to include active elapsed time
        self._load_today_time()

    def _reconcile_active_timer(self) -> None:
        """Handle 409 conflict: fetch running timer and restore UI state."""
        self._status_bar.set_message("Timer already running. Syncing state...", SUCCESS)
        self._check_active_timer()

    @property
    def is_timer_running(self) -> bool:
        return self._is_timer_active
        
    def get_running_entry_id(self) -> Optional[int]:
        if self._is_timer_active:
            return self._task_section._running_entry_id
        return None
