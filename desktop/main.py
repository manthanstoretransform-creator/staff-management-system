"""
SMS Desktop — Monitra-style PySide6 application entry point.
Initialises all services (unchanged from original) and wires the new UI.
"""
import sys
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from shiboken6 import isValid
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QMessageBox
)

# ── Existing service layer (UNCHANGED) ────────────────────────────────────────
from app.config import settings
from app.api.client import ApiClient
from app.auth.session import SessionManager
from app.auth.service import AuthService
from app.projects.service import ProjectService
from app.tasks.service import TaskService
from app.time_entries.service import TimeEntryService

# ── New UI layer ──────────────────────────────────────────────────────────────
from ui.login_window import LoginWindow
from ui.dashboard_window import DashboardWindow
from ui.styles import APP_QSS
from ui.workers import VerifySessionWorker

# ── Sync / Cache Layer ────────────────────────────────────────────────────────
from sync.local_cache import LocalCache
from sync.sync_queue import SyncQueue
from sync.network_monitor import NetworkMonitor

# ── Tracking Lifecycle Manager ────────────────────────────────────────────────
from tracking.manager import TrackingManager
from tracking.app_usage_tracker import AppUsageTracker
from ui.notification_manager import NotificationManager, create_app_icon


class MainWindow(QMainWindow):
    """
    Root application window.
    Coordinates the stacked widget swap: Login ↔ Dashboard.
    All service objects are created once and injected into the UI.
    """

    def __init__(
        self,
        auth_service: AuthService,
        session_manager: SessionManager,
        project_service: ProjectService,
        task_service: TaskService,
        time_entry_service: TimeEntryService,
        api_client: ApiClient,
        local_cache: Optional[LocalCache] = None,
        sync_queue: Optional[SyncQueue] = None,
        network_monitor: Optional[NetworkMonitor] = None,
        tracking_manager: Optional[TrackingManager] = None,
        notification_manager: Optional[NotificationManager] = None,
    ) -> None:
        super().__init__()
        self.auth_service = auth_service
        self.session_manager = session_manager
        self.project_service = project_service
        self.task_service = task_service
        self.time_entry_service = time_entry_service
        self.api_client = api_client
        self.local_cache = local_cache
        self.sync_queue = sync_queue
        self.network_monitor = network_monitor
        self.tracking_manager = tracking_manager
        self.notification_manager = notification_manager
        self._force_quit = False

        if self.notification_manager:
            self.notification_manager.restore_requested.connect(self.restore_window)
            self.notification_manager.quit_requested.connect(self.quit_application)

        self.setWindowTitle("Monitra — Staff Management")
        self.setMinimumSize(1024, 680)
        self.resize(1280, 800)

        self._init_ui()
        self._restore_session_on_startup()

    def _init_ui(self) -> None:
        self._stack = QStackedWidget(self)
        self.setCentralWidget(self._stack)

        # ── Login page ────────────────────────────────────────────
        self._login = LoginWindow(self.auth_service, self)
        self._login.login_success.connect(self._show_dashboard)

        # ── Dashboard page ────────────────────────────────────────
        self._dashboard = DashboardWindow(
            session_manager=self.session_manager,
            project_service=self.project_service,
            task_service=self.task_service,
            time_entry_service=self.time_entry_service,
            api_client=self.api_client,
            local_cache=self.local_cache,
            sync_queue=self.sync_queue,
            network_monitor=self.network_monitor,
            tracking_manager=self.tracking_manager,
            notification_manager=self.notification_manager,
            parent=self,
        )
        self._dashboard.logout_requested.connect(self._show_login)
        self._dashboard.unauthorized_error.connect(self._show_login)

        self._stack.addWidget(self._login)
        self._stack.addWidget(self._dashboard)
        self._stack.setCurrentWidget(self._login)

        # Application starts on Login screen
        self._stack.setCurrentWidget(self._login)

    def _restore_session_on_startup(self) -> None:
        """Attempt to restore session from local cache, verify with /auth/me in background."""
        if self.session_manager.restore_session():
            token = self.session_manager.access_token
            if token:
                self._login.show_checking_session()
                self._verify_worker = VerifySessionWorker(self.api_client, token)
                self._verify_worker.finished.connect(self._on_restore_success)
                self._verify_worker.error.connect(self._on_restore_error)
                self._verify_worker.start()

    def _on_restore_success(self, user_data: dict) -> None:
        """Called when startup session verification succeeds."""
        # Start the session in manager
        self.session_manager.start_session(self.session_manager.access_token, user_data)
        # Switch to dashboard
        self._show_dashboard(user_data)

    def _on_restore_error(self, exc: Exception) -> None:
        """Called when startup session verification fails."""
        from app.api.exceptions import ApiHttpError
        if isinstance(exc, ApiHttpError) and exc.status_code in (401, 403):
            # Token is expired or invalid
            self.auth_service.logout()
            self._login.reset()
            self._login.error_label.setText("Session expired. Please log in again.")
        else:
            # Connection error or other server-side issue. Work offline if cached info is present.
            if self.session_manager.user_info:
                # Use the cached session
                self._stack.setCurrentWidget(self._dashboard)
                self._dashboard.on_login(self.session_manager.user_info)
                if self.notification_manager:
                    self.notification_manager.show_warning("Working offline. Authentication server is unreachable.")
            else:
                self.auth_service.logout()
                self._login.reset()
                self._login.error_label.setText("Network error. Could not connect to authentication server.")

    def _show_dashboard(self, user_data: dict) -> None:
        """Switch to dashboard and initialise with user data."""
        self._stack.setCurrentWidget(self._dashboard)
        self._dashboard.on_login(user_data)
        if self.notification_manager:
            self.notification_manager.show_success("Logged in successfully")

    def _show_login(self) -> None:
        """Log out: clear session, reset dashboard, return to login."""
        # Stop tracking before clearing session
        if self.tracking_manager:
            try:
                self.tracking_manager.stop_tracking()
            except Exception:
                pass
        # Clear app usage cached records to prevent cross-user leakage
        if self.local_cache:
            try:
                self.local_cache.clear_app_usage()
            except Exception:
                pass
        self.auth_service.logout()          # clears token + session (existing)
        self._dashboard.reset_state()       # clears UI state
        self._login.reset()                 # clear login form
        self._stack.setCurrentWidget(self._login)
        if self.notification_manager:
            self.notification_manager.show_error("Your session has expired. Please log in again.")

    def _shutdown_app(self) -> None:
        """Gracefully stop background threads and close database connections."""
        if self.network_monitor:
            self.network_monitor.stop()
            self.network_monitor.wait(1000)
        if self.sync_queue:
            self.sync_queue.stop()
            self.sync_queue.wait(1000)
        if self.tracking_manager:
            try:
                w = getattr(self.tracking_manager, "_start_worker", None)
                if w and isValid(w):
                    w.terminate()
                    w.wait(500)
            except Exception:
                pass
            try:
                w = getattr(self.tracking_manager, "_stop_worker", None)
                if w and isValid(w):
                    w.terminate()
                    w.wait(500)
            except Exception:
                pass

        # Stop startup verification worker if running
        verify_w = getattr(self, "_verify_worker", None)
        if verify_w and isValid(verify_w):
            try:
                if verify_w.isRunning():
                    verify_w.terminate()
                    verify_w.wait(500)
            except Exception:
                pass

        # Stop dashboard data loading workers
        if getattr(self, "_dashboard", None):
            try:
                self._dashboard._safely_stop_worker("_projects_worker")
                self._dashboard._safely_stop_worker("_tasks_worker")
                self._dashboard._safely_stop_worker("_today_worker")
                self._dashboard._safely_stop_worker("_active_worker")
            except Exception:
                pass

        self.api_client.close()
        if self.local_cache:
            self.local_cache.close()

    def restore_window(self) -> None:
        self.show()
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def quit_application(self) -> None:
        self._force_quit = True
        self.close()

    def closeEvent(self, event) -> None:
        """Intercept close event with a Monitra-branded confirmation dialog (Quit, Minimize, or Cancel)."""
        if getattr(self, "_force_quit", False):
            # Bypass dialog and accept event
            pass
        else:
            from PySide6.QtCore import QSettings
            from ui.quit_confirm_dialog import QuitConfirmDialog
            from PySide6.QtWidgets import QDialog

            settings = QSettings("Monitra", "SMSDesktop")
            choice = settings.value("remember_exit_choice", "")

            # Only show dialog if user hasn't chosen "Remember my choice"
            if choice not in ("minimize", "quit"):
                dialog = QuitConfirmDialog(self)
                dialog.exec()
                choice = dialog.result_action or "cancel"

            if choice == "cancel":
                event.ignore()
                return

            if choice == "minimize":
                self.hide()  # Minimize to system tray by hiding the window
                if self.notification_manager:
                    self.notification_manager.show_info(
                        "Monitra minimized to system tray. Time tracking will continue in the background."
                    )
                event.ignore()
                return

        # choice is "quit"
        is_running = self.tracking_manager.is_tracking_active() if self.tracking_manager else self._dashboard.is_timer_running
        if is_running:
            if self.tracking_manager and self.tracking_manager.is_tracking_active():
                session = self.tracking_manager.get_active_session()
                entry_id = session["entry_id"]
                task_id = session["task_id"]
                # Freeze app trackers and save final segments locally
                for tracker in self.tracking_manager._trackers:
                    try:
                        tracker.stop_tracker()
                    except Exception:
                        pass
            else:
                entry_id = self._dashboard.get_running_entry_id()
                task_id = getattr(self._dashboard._task_section, "_running_task_id", None)

            # Reset UI timer active state
            self._dashboard._is_timer_active = False
            self._dashboard._sidebar.set_timer_active(False)
            self._dashboard._status_bar.set_timer_info("")

            # Clear running timer state in local cache so it won't resume on next launch
            if self.local_cache:
                self.local_cache.clear_app_state("timer_state")

            if entry_id and entry_id > 0:
                # Bounded fast sync of final segments synchronously on exit
                if self.local_cache:
                    try:
                        pending = self.local_cache.get_pending_app_usage()
                        records = [r for r in pending if r["time_entry_id"] == entry_id]
                        if records:
                            record_ids = [r["id"] for r in records]
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
                            self.time_entry_service.batch_sync_app_usage(entry_id, payload)
                            self.local_cache.complete_app_usage(record_ids)
                    except Exception:
                        pass

                try:
                    self.time_entry_service.stop_time_entry(entry_id, timeout=3.0)
                except Exception:
                    if self.local_cache:
                        self.local_cache.enqueue_action(
                            "stop_timer",
                            {"entry_id": entry_id, "task_id": task_id},
                            priority=1,
                            idempotency_key=f"stop_{entry_id}"
                        )
                        if self.sync_queue:
                            self.sync_queue.wake()

        self._shutdown_app()
        event.accept()


def main() -> None:
    # Initialize cache and synchronization queue
    local_cache = LocalCache()
    api_client = ApiClient()
    session_manager = SessionManager(local_cache=local_cache)
    auth_service = AuthService(api_client, session_manager)
    project_service = ProjectService(api_client)
    task_service = TaskService(api_client)
    time_entry_service = TimeEntryService(api_client)

    # Background threads
    sync_queue = SyncQueue(local_cache, time_entry_service, task_service)
    network_monitor = NetworkMonitor(api_client)

    # Start background threads
    network_monitor.start()
    sync_queue.start()

    app = QApplication(sys.argv)
    app.setApplicationName("Monitra")
    app.setApplicationDisplayName("Monitra — Staff Management")

    # Apply global stylesheet
    app.setStyleSheet(APP_QSS)

    # Use Segoe UI as default font (available on Windows; falls back gracefully)
    default_font = QFont("Segoe UI")
    default_font.setPointSize(11)
    app.setFont(default_font)

    # Initialize central tracking manager
    tracking_manager = TrackingManager(time_entry_service, local_cache)

    # Initialize application usage tracker
    app_usage_tracker = AppUsageTracker(local_cache)
    tracking_manager.register_tracker(app_usage_tracker)

    # Initialize notification manager
    notification_manager = NotificationManager(app)

    # Wire tracking manager signals to notification manager
    def on_tracking_started(session: dict) -> None:
        if session.get("is_switch"):
            notification_manager.show_info(f"Switched to \"{session.get('task_name', 'Task')}\"")
        else:
            task_name = session.get("task_name")
            msg = f"Tracking started for \"{task_name}\"" if task_name else "Tracking started"
            notification_manager.show_success(msg)

    def on_tracking_stopped(result: dict) -> None:
        if tracking_manager._is_switching_internal:
            return
        notification_manager.show_success("Tracking stopped")

    tracking_manager.tracking_started.connect(on_tracking_started)
    tracking_manager.tracking_stopped.connect(on_tracking_stopped)
    tracking_manager.error_occurred.connect(lambda err: notification_manager.show_error(err))

    # Apply global window icon
    app_icon = create_app_icon()
    app.setWindowIcon(app_icon)

    window = MainWindow(
        auth_service=auth_service,
        session_manager=session_manager,
        project_service=project_service,
        task_service=task_service,
        time_entry_service=time_entry_service,
        api_client=api_client,
        local_cache=local_cache,
        sync_queue=sync_queue,
        network_monitor=network_monitor,
        tracking_manager=tracking_manager,
        notification_manager=notification_manager,
    )
    window.show()

    # Run application
    exit_code = app.exec()

    # Safeguard: Ensure clean shutdown of background threads
    window._shutdown_app()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
