"""
Dashboard window — main application shell.

Assembles sidebar + top bar + task table + activity section.

Ownership: this widget owns no threads and no services. Every background
operation goes through `BackgroundApi`, which runs it on the runtime's bounded
pool and delivers the result back on the GUI thread.

This file is where the worst of the audited failures lived. `_on_queue_empty`
was connected to the sync queue's `queue_empty` signal, which the old consumer
emitted on every 500 ms poll of an empty queue rather than on the transition
into one. The slot then reloaded the project's tasks and today's time entries,
each spawning a fresh QThread. An idle, logged-in application therefore created
two OS threads and issued two HTTP requests every second, forever — measured at
48 threads in 25 seconds. Both halves are fixed: the service now emits an edge,
and this window schedules bounded, de-duplicated work rather than raw threads.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSplitter, QVBoxLayout, QWidget,
)

from app.api.client import ApiClient
from app.auth.session import SessionManager
from app.projects.service import ProjectService
from app.tasks.service import TaskService
from app.time_entries.service import TimeEntryService
from background_services.public_api import BackgroundApi, NetworkState, NotificationLevel
from core.logging_setup import get_logger
from core.time_format import ist_today
from ui import icons
from ui.activity_section import ActivitySection
from ui.sidebar import SidebarWidget
from ui.styles import (
    BORDER_LIGHT, CONTENT_BG, ERROR, PROJECT_COLORS, SUCCESS, TEXT_MUTED, WARNING,
)
from ui.stat_cards import StatCardsRow
from ui.task_table import TaskSection, is_task_completed
from ui.topbar import TopBar

log = get_logger("dashboard")

#: Background refresh cadence for project/task data while the window is open.
REFRESH_INTERVAL_MS = 120_000


class StatusBar(QFrame):
    """Thin status bar at the bottom of the dashboard."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(26)
        self.setStyleSheet(
            f"QFrame {{ background: #F1F5F9; border-top: 1px solid {BORDER_LIGHT}; }}"
        )
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

    def set_message(self, msg: str, color: Optional[str] = None) -> None:
        self._msg.setText(msg)
        self._msg.setStyleSheet(f"color: {color or TEXT_MUTED};")

    def set_timer_info(self, info: str) -> None:
        self._timer_status.setText(info)


class DashboardWindow(QWidget):
    """The signed-in application shell."""

    logout_requested = Signal()
    unauthorized_error = Signal()

    def __init__(
        self,
        runtime,
        session_manager: SessionManager,
        project_service: ProjectService,
        task_service: TaskService,
        time_entry_service: TimeEntryService,
        api_client: ApiClient,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.runtime = runtime
        self.api = BackgroundApi(runtime)
        self.session_manager = session_manager
        self.project_service = project_service
        self.task_service = task_service
        self.time_entry_service = time_entry_service
        self.api_client = api_client

        self._projects: List[Dict[str, Any]] = []
        self._current_project: Optional[Dict[str, Any]] = None
        self._current_project_color = PROJECT_COLORS[0]
        self._today_time_entries: List[Dict[str, Any]] = []
        #: The selected project's tasks, as last rendered. Held only so the
        #: summary cards can count completed vs total without re-fetching.
        self._project_tasks: List[Dict[str, Any]] = []
        self._pending_active_timer: Optional[Dict[str, Any]] = None
        self._had_pending_sync = False
        self._active = False
        #: The date currently selected in the top bar. Drives whether the
        #: live timer is allowed to bleed into the sidebar/task totals: a
        #: past date must show completed hours only, never a ticking value.
        self._current_date: date = ist_today()
        #: Whether the last committed network state was usable. Starts None so
        #: the first observation is not announced as a recovery — telling the
        #: user they are "back online" before they were ever seen offline was
        #: part of the reported notification noise.
        self._was_online: Optional[bool] = None
        #: How many fetches of the refresh currently in flight are still
        #: outstanding, and whether any of them failed. "Last sync" is only
        #: advanced once a refresh finishes with every fetch successful.
        self._refresh_outstanding = 0
        self._refresh_failed = False

        self._build_ui()
        self._wire_services()

        # Periodic refresh. A UI-only timer that schedules bounded work; it
        # does not create threads and does not run while signed out.
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh_data)

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setStyleSheet(f"QWidget {{ background: {CONTENT_BG}; }}")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        h_split = QWidget(self)
        h_layout = QHBoxLayout(h_split)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        self._sidebar = SidebarWidget(self)
        self._sidebar.project_selected.connect(self._on_project_selected)
        self._sidebar.logout_requested.connect(self._handle_logout)
        self._sidebar.refresh_requested.connect(self.refresh_data)
        h_layout.addWidget(self._sidebar)

        # Last-sync display: driven entirely by SyncService's own edge signal,
        # never a widget-local timer or guess. Shows the honest "Never" state
        # until the first sync actually completes this session.
        self.api.sync.synced_at_changed.connect(self._sidebar.set_last_synced_at)
        self._sidebar.set_last_synced_at(self.api.last_synced_at())

        right_col = QWidget(h_split)
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._topbar = TopBar(right_col)
        self._topbar.date_changed.connect(self._on_date_changed)
        self._topbar.refresh_requested.connect(self.refresh_data)
        right_layout.addWidget(self._topbar)

        # Task and Activity/Screenshot sections share the remaining height
        # via a drag-resizable splitter rather than a fixed 4:6 stretch
        # inside a scroll area -- each section already scrolls its own
        # content internally, so the outer container only needs to divide
        # up the available height, not add a second, redundant scrollbar.
        content_container = QWidget(right_col)
        content_container.setStyleSheet(f"background: {CONTENT_BG};")
        content_outer_layout = QVBoxLayout(content_container)
        content_outer_layout.setContentsMargins(20, 16, 20, 20)
        content_outer_layout.setSpacing(14)

        # ── Summary cards ─────────────────────────────────────────
        # Rendered from data this window already holds: the day's time
        # entries, the selected project's tasks and TimerService's session.
        # The row fetches nothing and counts nothing itself.
        self._stat_cards = StatCardsRow(content_container)
        content_outer_layout.addWidget(self._stat_cards)

        self._content_splitter = QSplitter(Qt.Orientation.Vertical, content_container)
        # A section collapsed to 0 height would look like it vanished --
        # each side keeps a usable minimum instead (enforced below).
        self._content_splitter.setChildrenCollapsible(False)
        self._content_splitter.setHandleWidth(10)
        self._content_splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {CONTENT_BG};
                border-top: 1px solid {BORDER_LIGHT};
                border-bottom: 1px solid {BORDER_LIGHT};
            }}
            QSplitter::handle:hover {{
                background: {BORDER_LIGHT};
            }}
        """)

        self._task_section = TaskSection(
            api=self.api, task_service=self.task_service,
            time_entry_service=self.time_entry_service, parent=self._content_splitter
        )
        self._task_section.timer_state_changed.connect(self._on_timer_state_changed)
        self._task_section.error_occurred.connect(self._on_error)
        self._task_section.active_timer_conflict.connect(self._reconcile_active_timer)
        self._task_section.task_action_succeeded.connect(self._on_task_action_succeeded)
        self._task_section.refresh_requested.connect(self.refresh_data)
        # The Request (manual time entry) button lives in the top bar, but
        # the dialog and its submission stay in TaskSection -- this is the
        # only wire between them.
        self._topbar.request_clicked.connect(self._task_section.open_manual_entry_dialog)
        # Add Task and the search field live in the top bar; the dialog, the
        # create call and the filtering all still belong to TaskSection.
        self._topbar.add_task_clicked.connect(self._task_section.open_add_task_dialog)
        self._topbar.search_changed.connect(self._task_section.apply_search)
        self._task_section.add_task_available.connect(self._topbar.set_add_task_enabled)
        self._task_section.setMinimumHeight(220)
        self._content_splitter.addWidget(self._task_section)

        self._activity_section = ActivitySection(self.api, self.api_client, self._content_splitter)
        self._activity_section.setMinimumHeight(220)
        self._content_splitter.addWidget(self._activity_section)

        # Initial split mirrors the previous 4:6 stretch-factor proportion;
        # the user can drag it anywhere between the two minimums afterward.
        self._content_splitter.setStretchFactor(0, 4)
        self._content_splitter.setStretchFactor(1, 6)
        self._content_splitter.setSizes([400, 600])

        content_outer_layout.addWidget(self._content_splitter)
        right_layout.addWidget(content_container, 1)

        h_layout.addWidget(right_col, 1)
        root_layout.addWidget(h_split, 1)

        self._status_bar = StatusBar(self)
        root_layout.addWidget(self._status_bar)

    def _wire_services(self) -> None:
        """
        Subscribe to the background services.

        Every one of these is an edge-triggered signal. Nothing here is wired
        to a polling signal, which is the invariant that keeps an idle
        application idle.
        """
        sync = self.api.sync
        sync.pending_count_changed.connect(self._on_pending_count_changed)
        sync.queue_drained.connect(self._on_queue_drained)

        network = self.api.network
        network.network_state_changed.connect(self._on_network_state_changed)
        network.latency_measured.connect(self._topbar.set_latency)
        self._topbar.set_network_state(network.network_state)

        timer = self.api.timer
        timer.timer_tick.connect(self._on_timer_tick)
        timer.timer_recovered.connect(self._on_timer_recovered)

        # Unwanted-activity warnings: edge-triggered by the rule engine (one
        # emission per threshold crossing, already cooldown-throttled there);
        # the notification key gives NotificationService a second layer of
        # de-duplication on top.
        activity = self.api.activity
        activity.unwanted_activity_alert.connect(self._on_unwanted_activity_alert)

    def _on_unwanted_activity_alert(self, message: str) -> None:
        self.api.notify(message, NotificationLevel.WARNING, key="unwanted-activity")

    # ── Session lifecycle ─────────────────────────────────────────────────────

    def on_login(self, user_data: dict) -> None:
        """
        Initialise the dashboard for a signed-in user.

        Cache first: everything already known locally is rendered immediately,
        then a single round of background refreshes reconciles it. The user is
        never made to wait on the network to reach a usable screen.
        """
        self._active = True
        self._sidebar.set_user(user_data)
        self._task_section.set_user_role(user_data.get("role_name"))
        self._task_section.set_user_id(user_data.get("id"))
        self._activity_section.set_enabled(True)

        self._render_cached_projects()

        self._refresh_timer.start(REFRESH_INTERVAL_MS)
        self.refresh_data()
        self._load_task_statuses()
        self._check_active_timer()
        self._load_today_time()

    def on_session_verified(self, user_data: dict) -> None:
        """The restored token was confirmed by the backend."""
        self._sidebar.set_user(user_data)
        self._task_section.set_user_role(user_data.get("role_name"))
        self._task_section.set_user_id(user_data.get("id"))

    def reset_state(self) -> None:
        """Clear everything session-scoped on logout."""
        self._active = False
        self._refresh_timer.stop()
        self._activity_section.set_enabled(False)
        self.api.cancel_key("load-projects")
        self.api.cancel_key("load-tasks")
        self.api.cancel_key("load-today")
        self.api.cancel_key("load-statuses")
        self.api.cancel_key("check-active-timer")

        # Those cancellations mean the in-flight refresh's steps will never
        # report back; clear the round so the next session can refresh.
        self._refresh_outstanding = 0
        self._refresh_failed = False

        self._projects = []
        self._current_project = None
        self._today_time_entries = []
        self._pending_active_timer = None
        self._sidebar.set_projects([])
        self._sidebar.set_timer_active(False)
        self._sidebar.set_active_timer_project(None)
        self._sidebar.set_total_seconds(0)
        self._task_section.set_all_projects([])
        self._task_section.clear()
        self._project_tasks = []
        self._stat_cards.reset()
        self._status_bar.set_message("Ready")
        self._status_bar.set_timer_info("")

    def _handle_logout(self) -> None:
        self.reset_state()
        self.logout_requested.emit()

    # ── Projects ──────────────────────────────────────────────────────────────

    def _render_cached_projects(self) -> None:
        cached = self.api.cache.get_cached_projects()
        if cached:
            self._projects = cached
            self._sidebar.set_projects(cached)
            self._task_section.set_all_projects(cached)
            self._status_bar.set_message("Loaded projects from cache.")
            self._apply_active_timer_if_ready()
        else:
            self._status_bar.set_message("Loading projects…")

    def load_projects(self, on_done: Optional[Callable[[bool], None]] = None) -> bool:
        """Refresh projects from the backend.

        :param on_done: Called with True/False once the fetch succeeded or
            failed, after the normal handler has run. Used by refresh_data to
            decide whether the refresh as a whole succeeded.
        :return: False if the request was de-duplicated against one already in
            flight, in which case `on_done` is never called.
        """
        return self._run_load(
            self.project_service.get_projects,
            self._on_projects_loaded,
            self._on_projects_error,
            key="load-projects",
            on_done=on_done,
        )

    def _run_load(
        self,
        call: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[BaseException], None],
        *,
        key: str,
        on_done: Optional[Callable[[bool], None]] = None,
    ) -> bool:
        """Submit one background fetch, reporting its outcome to `on_done`.

        A thin wrapper over api.run_in_background so every loader reports
        success or failure the same way, without any of them growing a second
        code path for the refresh case.
        """
        def succeeded(result: Any) -> None:
            on_success(result)
            if on_done is not None:
                on_done(True)

        def failed(exc: BaseException) -> None:
            on_error(exc)
            if on_done is not None:
                on_done(False)

        return self.api.run_in_background(
            call, on_success=succeeded, on_error=failed, key=key
        ) is not None

    def _on_projects_loaded(self, projects: list) -> None:
        self._projects = projects
        self._sidebar.set_projects(projects)
        self._task_section.set_all_projects(projects)
        self.api.cache.cache_projects(projects)
        if projects:
            # The count now lives in the sidebar's "PROJECTS (N)" header --
            # repeating it here would just be stale, duplicate information.
            self._status_bar.set_message("Ready")
            self._apply_active_timer_if_ready()
        else:
            self._status_bar.set_message("No projects found.", TEXT_MUTED)
            self._task_section.clear()

    def _on_projects_error(self, exc: BaseException) -> None:
        # Cached data stays on screen. A failed request must not blank a view
        # that is already showing valid local data.
        #
        # It must not touch the connectivity pill either: one failed request is
        # not a connectivity measurement. Ask NetworkService to probe now and
        # let it decide -- it owns that state.
        if self._projects:
            self.api.network.check_now()
            self._status_bar.set_message("Showing cached projects — retrying.", WARNING)
            return
        self._status_bar.set_message(f"Could not load projects: {exc}", ERROR)
        if "session expired" in str(exc).lower():
            self.unauthorized_error.emit()

    def _on_project_selected(self, project: Dict[str, Any]) -> None:
        self._current_project = project
        project_id = project.get("id")
        project_name = project.get("project_name", "Project")

        index = next(
            (i for i, p in enumerate(self._projects) if p.get("id") == project_id), 0
        )
        self._current_project_color = PROJECT_COLORS[index % len(PROJECT_COLORS)]
        self._sidebar.select_project(project_id)

        cached_tasks = self.api.cache.get_cached_tasks(project_id)
        if cached_tasks is not None:
            self._render_tasks(cached_tasks, from_cache=True)
        else:
            self._task_section.set_loading(project_name)

        self._load_tasks(project_id)

    def _load_tasks(
        self, project_id: int, on_done: Optional[Callable[[bool], None]] = None
    ) -> bool:
        return self._run_load(
            lambda: self.task_service.get_tasks_for_project(project_id),
            lambda tasks: self._on_tasks_loaded(project_id, tasks),
            self._on_tasks_error,
            key=f"load-tasks:{project_id}",
            on_done=on_done,
        )

    def _on_tasks_loaded(self, project_id: int, tasks: list) -> None:
        # Ignore a response for a project the user has since navigated away
        # from: a slow reply must never overwrite a newer selection.
        if not self._current_project or self._current_project.get("id") != project_id:
            log.debug("discarding tasks for project %s; selection moved on", project_id)
            return
        self.api.cache.cache_tasks(project_id, tasks)
        self._render_tasks(tasks, from_cache=False)

    def _on_tasks_error(self, exc: BaseException) -> None:
        if getattr(self._task_section, "_has_loaded_tasks", False):
            # See _on_projects_error: the pill belongs to NetworkService.
            self.api.network.check_now()
            self._status_bar.set_message("Showing cached tasks — retrying.", WARNING)
            return
        self._task_section.set_error(str(exc))
        self._status_bar.set_message(f"Could not load tasks: {exc}", ERROR)
        if "session expired" in str(exc).lower():
            self.unauthorized_error.emit()

    def _render_tasks(self, tasks: list, from_cache: bool) -> None:
        for task in tasks:
            task["time_tracked_seconds"] = self._banked_seconds_by_task().get(task.get("id"), 0)
        self._task_section.set_tasks(tasks, self._current_project, self._current_project_color)
        self._project_tasks = tasks or []
        self._update_stat_cards()
        self._status_bar.set_message(
            "Loaded tasks from cache." if from_cache else f"{len(tasks)} tasks loaded."
        )

    # ── Summary cards ─────────────────────────────────────────────────────────

    def _update_stat_cards(self) -> None:
        """Push a fresh snapshot into the four summary cards.

        Everything here is read from state this window already loaded. No
        request is made, no duration is counted: the live session's elapsed
        seconds come from TimerService, exactly as the sidebar total does,
        and only for today -- a past date shows its completed hours alone.
        """
        entries = self._today_time_entries
        finished = [
            e for e in entries
            if e.get("status") in ("stopped", "completed") or e.get("end_time")
        ]
        banked = sum(e.get("total_seconds", 0) for e in finished)

        viewing_today = self._current_date == ist_today()
        running = self.api.is_timer_running()
        live = self.api.timer_elapsed_seconds() if (running and viewing_today) else 0
        self._stat_cards.set_total_seconds(banked + live, running and viewing_today)

        # Tasks completed: the selected project's own tasks, by the server's
        # status. Nothing is inferred -- a project with no tasks loaded shows
        # the "no project selected" state rather than 0 / 0.
        tasks = self._project_tasks
        if self._current_project and tasks:
            completed = sum(1 for t in tasks if is_task_completed(t))
            self._stat_cards.set_tasks_completed(completed, len(tasks))
        else:
            self._stat_cards.set_tasks_completed(None, None)

        session = self.api.active_session() or {} if running else {}
        self._stat_cards.set_active_task(
            session.get("task_name") if running else None,
            session.get("project_name") or self._project_name_for(session.get("project_id")),
        )

        self._stat_cards.set_work_day(*self._work_day_span(entries))

    def _project_name_for(self, project_id: Optional[int]) -> Optional[str]:
        if project_id is None:
            return None
        for project in self._projects:
            if project.get("id") == project_id:
                return project.get("project_name")
        return None

    def _work_day_span(self, entries: List[Dict[str, Any]]):
        """(span_seconds, first_label, last_label) for the viewed day.

        The span is first tracked start -> last tracked end, i.e. how long
        the working day has been open, which is a different fact from the
        tracked total (that is the first card). Returns (None, None, None)
        when the day holds no usable timestamps -- the card then says "No
        time logged" rather than showing a measured-looking zero.
        """
        from datetime import datetime

        def parse(value: Optional[str]) -> Optional[datetime]:
            if not value:
                return None
            try:
                return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                return None

        starts = [parse(e.get("start_time")) for e in entries]
        ends = [parse(e.get("end_time")) or parse(e.get("start_time")) for e in entries]
        starts = [value for value in starts if value is not None]
        ends = [value for value in ends if value is not None]
        if not starts or not ends:
            return None, None, None

        first, last = min(starts), max(ends)
        if last < first:
            return None, None, None
        span = int((last - first).total_seconds())
        return (
            span,
            first.astimezone().strftime("%H:%M"),
            last.astimezone().strftime("%H:%M"),
        )

    # ── Today's time ──────────────────────────────────────────────────────────

    def _banked_seconds_by_task(self) -> Dict[int, int]:
        """Completed seconds per task for the currently displayed day."""
        totals: Dict[int, int] = {}
        for entry in self._today_time_entries:
            task_id = entry.get("task_id")
            if not task_id:
                continue
            if entry.get("status") in ("stopped", "completed") or entry.get("end_time"):
                totals[task_id] = totals.get(task_id, 0) + entry.get("total_seconds", 0)
        return totals

    def _load_today_time(
        self,
        target_date: Optional[date] = None,
        on_done: Optional[Callable[[bool], None]] = None,
    ) -> bool:
        target = target_date or ist_today()

        cached = self.api.cache.get_cached_time_entries(target.isoformat())
        if cached:
            self._apply_time_entries(cached, target, update_cache=False)

        api_client = self.api_client

        def call():
            from datetime import datetime

            start = datetime(target.year, target.month, target.day, 0, 0, 0).isoformat()
            end = datetime(target.year, target.month, target.day, 23, 59, 59).isoformat()
            response = api_client.get(
                "/time-entries",
                params={"start_date": start, "end_date": end, "limit": 1000},
            )
            data = response.json()
            return data if isinstance(data, list) else []

        return self._run_load(
            call,
            lambda entries: self._apply_time_entries(entries, target, True),
            lambda exc: log.info("could not refresh today's entries: %s", exc),
            key=f"load-today:{target.isoformat()}",
            on_done=on_done,
        )

    def _apply_time_entries(
        self, entries: list, target: date, update_cache: bool = True
    ) -> None:
        self._today_time_entries = entries
        banked = sum(
            e.get("total_seconds", 0)
            for e in entries
            if e.get("status") in ("stopped", "completed") or e.get("end_time")
        )

        # Add the live session only for today, and take its value from the
        # timer service rather than from any widget.
        live = 0
        if target == ist_today() and self.api.is_timer_running():
            live = self.api.timer_elapsed_seconds()
        self._sidebar.set_total_seconds(banked + live)

        if update_cache:
            self.api.cache.cache_time_entries(target.isoformat(), entries)

        self._task_section.update_tasks_tracked_times(self._banked_seconds_by_task())
        self._update_stat_cards()

    def _on_date_changed(self, target_date: date) -> None:
        self._current_date = target_date
        self._task_section.set_viewing_date(target_date)
        self._status_bar.set_message(f"Loading data for {target_date}…")
        self._load_today_time(target_date)

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh_data(self) -> None:
        """
        Re-fetch everything the dashboard displays: projects, task statuses,
        the selected project's tasks, and the viewed day's time entries. Each
        fetch caches its result and re-renders its own widgets, so the screen
        shows the backend's current data rather than the previous snapshot.

        "Last sync" is advanced only once every fetch of the round has come
        back successfully -- a refresh that failed, wholly or partly, leaves
        the previous timestamp alone and reports itself through each loader's
        existing error handling.

        Skipped entirely while the backend is unusable: refreshing into a known
        outage produces nothing but retry noise and reconnect storms.
        """
        if not self._active:
            return
        if self.api.network_state() not in NetworkState.USABLE:
            log.debug("skipping refresh; network is %s", self.api.network_state())
            self._status_bar.set_message(
                "Offline — showing the last data received.", WARNING
            )
            return
        if self._refresh_outstanding:
            log.debug("refresh already in flight; ignoring")
            return

        self._refresh_failed = False
        # Callbacks are queued onto this thread, so none of them can run
        # before this method returns -- the count is complete before the
        # first step can decrement it.
        started = sum((
            self.load_projects(on_done=self._on_refresh_step),
            self._load_task_statuses(on_done=self._on_refresh_step),
            self._load_today_time(self._current_date, on_done=self._on_refresh_step),
            self._load_tasks(self._current_project.get("id"), on_done=self._on_refresh_step)
            if self._current_project else False,
        ))
        self._refresh_outstanding = started
        if started:
            self._status_bar.set_message("Refreshing…")

    def _on_refresh_step(self, ok: bool) -> None:
        """One fetch of the in-flight refresh finished."""
        if self._refresh_outstanding <= 0:
            return
        self._refresh_outstanding -= 1
        self._refresh_failed = self._refresh_failed or not ok
        if self._refresh_outstanding:
            return

        if self._refresh_failed:
            # The failing loader has already reported it and kept the cached
            # view on screen. Claiming a sync that did not happen would be
            # worse than showing the older timestamp.
            log.info("refresh completed with errors; last-sync left unchanged")
            return
        self.api.note_pull_succeeded()
        self._status_bar.set_message("Refreshed.")

    def _load_task_statuses(
        self, on_done: Optional[Callable[[bool], None]] = None
    ) -> bool:
        return self._run_load(
            self.task_service.get_task_statuses,
            self.api.cache.cache_task_statuses,
            lambda exc: log.info("could not load task statuses: %s", exc),
            key="load-statuses",
            on_done=on_done,
        )

    # ── Timer ─────────────────────────────────────────────────────────────────

    def _on_timer_state_changed(self, active: bool) -> None:
        self._sidebar.set_timer_active(active)
        self._update_stat_cards()
        if active:
            session = self.api.active_session() or {}
            self._sidebar.set_active_timer_project(session.get("project_id"))
            self._status_bar.set_timer_info(f"{icons.img_tag('circle_filled', SUCCESS, 10)} Timer running")
            self._status_bar.set_message("Tracking time…")
        else:
            self._sidebar.set_active_timer_project(None)
            self._status_bar.set_timer_info("")
            self._status_bar.set_message("Timer stopped.")
            # Re-read today's totals now the entry has been banked.
            self._load_today_time()

    def _on_timer_tick(self, elapsed: int) -> None:
        """
        Keep the sidebar total live without re-querying anything.

        Only while today is the date on screen. The timer keeps running
        regardless of which date is being viewed, but `_today_time_entries`
        reflects whatever date was last loaded -- if the user has navigated
        to view a past date, folding today's live `elapsed` seconds into that
        day's completed-hours total would silently mix the two. A past date
        must show completed hours only; _apply_time_entries() already set
        that value when the date changed, so this tick is simply skipped.
        """
        if self._current_date != ist_today():
            return
        banked = sum(
            e.get("total_seconds", 0)
            for e in self._today_time_entries
            if e.get("status") in ("stopped", "completed") or e.get("end_time")
        )
        self._sidebar.set_total_seconds(banked + elapsed)
        self._update_stat_cards()

    def _on_timer_recovered(self, session: dict) -> None:
        elapsed = self.api.timer_elapsed_seconds()
        log.info("timer recovered in UI: task %s, %ds", session.get("task_id"), elapsed)
        self._sidebar.set_timer_active(True)
        self._sidebar.set_active_timer_project(session.get("project_id"))
        self._status_bar.set_message("Recovered a timer that was still running.", SUCCESS)
        self.api.notify(
            "Recovered a timer that was still running from your last session.",
            NotificationLevel.INFO, key="timer-recovered",
        )

    def _check_active_timer(self) -> None:
        """Ask the backend whether it believes a timer is running."""
        api_client = self.api_client

        def call():
            response = api_client.get("/time-entries", params={"status": "running", "limit": 1})
            entries = response.json()
            if isinstance(entries, list):
                return next((e for e in entries if e.get("end_time") is None), None)
            return None

        self.api.run_in_background(
            call,
            on_success=self._on_active_timer_checked,
            on_error=lambda exc: log.info("could not check for an active timer: %s", exc),
            key="check-active-timer",
        )

    def _on_active_timer_checked(self, active_entry: Optional[dict]) -> None:
        if not active_entry or "id" not in active_entry:
            return
        self._pending_active_timer = active_entry
        self._apply_active_timer_if_ready()

    def _apply_active_timer_if_ready(self) -> None:
        """
        Adopt a backend-reported running entry once projects are available.

        The timer service re-anchors to the server's `start_time`, so the
        displayed elapsed value matches the record that will be billed.
        """
        entry = self._pending_active_timer
        if not entry or not self._projects:
            return
        self._pending_active_timer = None

        self.api.timer.adopt_remote_session(entry)

        project_id = entry.get("project_id")
        task_id = entry.get("task_id")
        self._sidebar.set_timer_active(True)
        self._sidebar.set_active_timer_project(project_id)

        if self._current_project and self._current_project.get("id") == project_id:
            self._task_section.sync_active_timer(
                task_id, entry.get("id"), self.api.timer_elapsed_seconds()
            )
        else:
            for project in self._projects:
                if project.get("id") == project_id:
                    self._on_project_selected(project)
                    break

        self._load_today_time()

    def _reconcile_active_timer(self) -> None:
        """Handle a 409 conflict by re-reading the server's view of the truth."""
        self._status_bar.set_message("A timer is already running. Syncing state…", SUCCESS)
        self._check_active_timer()

    # ── Sync ──────────────────────────────────────────────────────────────────

    def _on_pending_count_changed(self, pending: int) -> None:
        self._topbar.set_sync_status(pending)
        if pending > 0:
            self._had_pending_sync = True

    def _on_queue_drained(self) -> None:
        """
        Everything queued has now synced.

        This fires once, on the transition into an empty queue — not on every
        poll of one. That distinction is what removed the two-threads-per-second
        storm; see the module docstring.
        """
        if not self._had_pending_sync:
            return
        self._had_pending_sync = False
        self.api.notify(
            "Pending activity synced successfully.",
            NotificationLevel.SUCCESS, key="sync-drained",
        )
        # Re-read what the server now holds, once.
        self._load_today_time()
        if self._current_project:
            self._load_tasks(self._current_project.get("id"))

    # ── Network ───────────────────────────────────────────────────────────────

    def _on_network_state_changed(self, state: str) -> None:
        usable = state in NetworkState.USABLE
        recovered = usable and self._was_online is False
        self._topbar.set_network_state(state)

        if usable:
            self._status_bar.set_message("Online", SUCCESS)
            # Only announce a *recovery*. Announcing the first observation
            # would tell the user they are "back online" before they had ever
            # been seen offline.
            if recovered:
                self.api.notify(
                    "Back online. Syncing pending activity.",
                    NotificationLevel.SUCCESS, key="network-online",
                )
            if not self._projects:
                self.load_projects()
            self.refresh_data()
        elif state == NetworkState.NO_NETWORK:
            self._status_bar.set_message("No network — showing cached data.", WARNING)
            self.api.notify(
                "You are offline. Your activity is saved locally and will sync automatically.",
                NotificationLevel.WARNING, key="network-offline",
            )
        else:
            # The machine has a network; the backend is the problem. Say so,
            # rather than telling the user their internet is down.
            self._status_bar.set_message("Server unreachable — showing cached data.", WARNING)
            self.api.notify(
                "The Monitra server is unreachable. Your activity is saved locally.",
                NotificationLevel.WARNING, key="network-backend-down",
            )

        self._was_online = usable

    # ── Misc ──────────────────────────────────────────────────────────────────

    def _on_task_action_succeeded(self, message: str) -> None:
        self._status_bar.set_message(message, SUCCESS)
        self.api.notify(message, NotificationLevel.SUCCESS, key=f"task-action:{message}")

    def _on_error(self, message: str) -> None:
        self._status_bar.set_message(f"Error: {message}", ERROR)
        if "session expired" in message.lower():
            self.unauthorized_error.emit()

    # ── Compatibility accessors ───────────────────────────────────────────────

    @property
    def is_timer_running(self) -> bool:
        return self.api.is_timer_running()

    def get_running_entry_id(self) -> Optional[int]:
        session = self.api.active_session()
        return session.get("entry_id") if session else None
