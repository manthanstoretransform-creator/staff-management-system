import sys
from typing import Optional, List, Dict, Any
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QComboBox,
    QMessageBox
)

from app.config import settings
from app.api.client import ApiClient
from app.auth.session import SessionManager
from app.auth.service import AuthService
from app.projects.service import ProjectService
from app.tasks.service import TaskService
from app.timer.engine import TimerEngine, TimerState
from app.time_entries.service import TimeEntryService

class LoginWorker(QThread):
    """Background worker QThread to handle synchronous authentication without blocking the UI thread."""
    
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


class LoginWidget(QWidget):
    """Widget containing the Login interface inputs, credentials submission, and progress tracking."""
    
    login_success = Signal(dict)

    def __init__(self, auth_service: AuthService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.auth_service = auth_service
        self.worker: Optional[LoginWorker] = None
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        # Title Label
        title_label = QLabel("SMS Desktop", self)
        title_font = title_label.font()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Subtitle
        subtitle_label = QLabel("Sign in to your workforce account", self)
        subtitle_label.setStyleSheet("color: #64748B;")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle_label)
        layout.addSpacing(10)

        # Username / Email Input
        self.username_input = QLineEdit(self)
        self.username_input.setPlaceholderText("Email or Username")
        self.username_input.setFixedWidth(280)
        self.username_input.setStyleSheet("padding: 8px; border-radius: 4px; border: 1px solid #CBD5E1;")
        layout.addWidget(self.username_input, alignment=Qt.AlignmentFlag.AlignCenter)

        # Password Input
        self.password_input = QLineEdit(self)
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFixedWidth(280)
        self.password_input.setStyleSheet("padding: 8px; border-radius: 4px; border: 1px solid #CBD5E1;")
        layout.addWidget(self.password_input, alignment=Qt.AlignmentFlag.AlignCenter)

        # Error Status Label
        self.error_label = QLabel("", self)
        self.error_label.setFixedWidth(280)
        self.error_label.setStyleSheet("color: #EF4444;")
        self.error_label.setWordWrap(True)
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.error_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Login Submit Button
        self.login_button = QPushButton("Log In", self)
        self.login_button.setFixedWidth(280)
        self.login_button.setStyleSheet(
            "background-color: #2563EB; color: white; padding: 10px; "
            "border-radius: 4px; font-weight: bold; border: none;"
        )
        self.login_button.clicked.connect(self.handle_login)
        layout.addWidget(self.login_button, alignment=Qt.AlignmentFlag.AlignCenter)

    def handle_login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            self.error_label.setText("Fields cannot be empty.")
            return

        self.error_label.setText("")
        self.set_loading(True)

        self.worker = LoginWorker(self.auth_service, username, password)
        self.worker.finished.connect(self.on_login_success)
        self.worker.error.connect(self.on_login_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        self.worker.start()

    def set_loading(self, loading: bool) -> None:
        self.username_input.setEnabled(not loading)
        self.password_input.setEnabled(not loading)
        self.login_button.setEnabled(not loading)
        if loading:
            self.login_button.setText("Logging in...")
            self.login_button.setStyleSheet(
                "background-color: #93C5FD; color: white; padding: 10px; "
                "border-radius: 4px; font-weight: bold; border: none;"
            )
        else:
            self.login_button.setText("Log In")
            self.login_button.setStyleSheet(
                "background-color: #2563EB; color: white; padding: 10px; "
                "border-radius: 4px; font-weight: bold; border: none;"
            )

    def on_login_success(self, user_data: dict) -> None:
        self.set_loading(False)
        self.password_input.clear()
        self.login_success.emit(user_data)

    def on_login_error(self, error_message: str) -> None:
        self.set_loading(False)
        self.error_label.setText(error_message)


class LoadProjectsWorker(QThread):
    """Background worker QThread to fetch user projects without blocking UI."""
    
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
    """Background worker QThread to fetch project tasks without blocking UI."""
    
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
    """Background worker QThread to initiate backend time entry registration."""
    
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
    """Background worker QThread to stop/finalize active backend time entry."""
    
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, time_entry_service: TimeEntryService, entry_id: int) -> None:
        super().__init__()
        self.time_entry_service = time_entry_service
        self.entry_id = entry_id

    def run(self) -> None:
        try:
            result = self.time_entry_service.stop_time_entry(self.entry_id)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class DashboardPlaceholder(QWidget):
    """Core view window managing project/task selections, visual timer display, and backend synchronizations."""
    
    logout_requested = Signal()
    unauthorized_error = Signal()

    def __init__(
        self,
        session_manager: SessionManager,
        project_service: ProjectService,
        task_service: TaskService,
        time_entry_service: TimeEntryService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.session_manager = session_manager
        self.project_service = project_service
        self.task_service = task_service
        self.time_entry_service = time_entry_service
        
        self.timer_engine = TimerEngine()
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.update_timer_display)

        self.current_time_entry_id: Optional[int] = None
        self.projects_list: List[Dict[str, Any]] = []
        self.tasks_list: List[Dict[str, Any]] = []
        
        self.projects_worker: Optional[LoadProjectsWorker] = None
        self.tasks_worker: Optional[LoadTasksWorker] = None
        self.start_worker: Optional[StartTimeEntryWorker] = None
        self.stop_worker: Optional[StopTimeEntryWorker] = None
        
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        # Header Title
        title_label = QLabel("SMS Desktop", self)
        title_font = title_label.font()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # User Info Profile Card
        self.user_info_label = QLabel("Logged in as: N/A", self)
        self.user_info_label.setStyleSheet("color: #475569; font-weight: bold;")
        self.user_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.user_info_label)
        layout.addSpacing(5)

        # Project Selection Dropdown label
        project_title = QLabel("Project", self)
        project_title.setStyleSheet("color: #64748B; font-size: 10pt; font-weight: bold;")
        layout.addWidget(project_title)

        # Project Dropdown (QComboBox)
        self.project_dropdown = QComboBox(self)
        self.project_dropdown.setFixedWidth(300)
        self.project_dropdown.setStyleSheet("padding: 6px; border-radius: 4px; border: 1px solid #CBD5E1;")
        self.project_dropdown.currentIndexChanged.connect(self.on_project_changed)
        layout.addWidget(self.project_dropdown)

        # Task Selection Dropdown label
        task_title = QLabel("Task", self)
        task_title.setStyleSheet("color: #64748B; font-size: 10pt; font-weight: bold;")
        layout.addWidget(task_title)

        # Task Dropdown (QComboBox)
        self.task_dropdown = QComboBox(self)
        self.task_dropdown.setFixedWidth(300)
        self.task_dropdown.setStyleSheet("padding: 6px; border-radius: 4px; border: 1px solid #CBD5E1;")
        self.task_dropdown.currentIndexChanged.connect(self.on_task_changed)
        layout.addWidget(self.task_dropdown)
        layout.addSpacing(5)

        # Digital Timer Display Label
        self.timer_display = QLabel("00:00:00", self)
        self.timer_display.setStyleSheet("font-family: monospace; font-size: 26pt; font-weight: bold; color: #1E293B;")
        self.timer_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.timer_display)

        # START / STOP Toggle Button
        self.start_stop_button = QPushButton("START", self)
        self.start_stop_button.setFixedWidth(300)
        self.start_stop_button.setEnabled(False)
        self.start_stop_button.setStyleSheet(
            "background-color: #2563EB; color: white; padding: 10px; "
            "border-radius: 4px; font-weight: bold; border: none;"
        )
        self.start_stop_button.clicked.connect(self.toggle_timer)
        layout.addWidget(self.start_stop_button)

        # Status text indicator
        self.status_label = QLabel("", self)
        self.status_label.setFixedWidth(300)
        self.status_label.setStyleSheet("color: #64748B; font-weight: bold;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(5)

        # Action Buttons Layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        # Refresh Button
        self.refresh_button = QPushButton("Refresh Projects", self)
        self.refresh_button.setFixedWidth(145)
        self.refresh_button.setStyleSheet(
            "background-color: #F1F5F9; color: #334155; padding: 10px; "
            "border-radius: 4px; font-weight: bold; border: 1px solid #E2E8F0;"
        )
        self.refresh_button.clicked.connect(self.trigger_load_projects)
        btn_layout.addWidget(self.refresh_button)

        # Logout Button
        self.logout_button = QPushButton("Log Out", self)
        self.logout_button.setFixedWidth(145)
        self.logout_button.setStyleSheet(
            "background-color: #EF4444; color: white; padding: 10px; "
            "border-radius: 4px; font-weight: bold; border: none;"
        )
        self.logout_button.clicked.connect(self.handle_logout)
        btn_layout.addWidget(self.logout_button)

        layout.addLayout(btn_layout)

    def populate_user_profile(self) -> None:
        """Fetch active details from session manager and update header."""
        user = self.session_manager.user_info
        if user:
            name = user.get("name", "User")
            role = user.get("role_name", "employee").upper()
            self.user_info_label.setText(f"Logged in as: {name} ({role})")

    def trigger_load_projects(self) -> None:
        """Trigger background fetching of projects."""
        self.status_label.setText("")
        self.status_label.setStyleSheet("color: #64748B;")
        self.start_stop_button.setEnabled(False)
        
        # Lock dropdowns during retrieve
        self.project_dropdown.clear()
        self.project_dropdown.addItem("Loading projects...")
        self.project_dropdown.setEnabled(False)
        self.task_dropdown.clear()
        self.task_dropdown.addItem("Select project first")
        self.task_dropdown.setEnabled(False)
        self.refresh_button.setEnabled(False)

        self.projects_worker = LoadProjectsWorker(self.project_service)
        self.projects_worker.finished.connect(self.on_projects_loaded)
        self.projects_worker.error.connect(self.on_projects_load_error)
        self.projects_worker.finished.connect(self.projects_worker.deleteLater)
        self.projects_worker.error.connect(self.projects_worker.deleteLater)
        self.projects_worker.start()

    def on_projects_loaded(self, projects: list) -> None:
        self.refresh_button.setEnabled(True)
        self.project_dropdown.clear()
        self.projects_list = projects

        if not projects:
            self.project_dropdown.addItem("No projects available")
            self.project_dropdown.setEnabled(False)
            return

        # Add default placeholder selection at index 0
        self.project_dropdown.addItem("[ Select Project ]")
        for project in projects:
            self.project_dropdown.addItem(project.get("project_name", "Unnamed Project"))
        
        self.project_dropdown.setEnabled(True)

    def on_projects_load_error(self, error_message: str) -> None:
        self.refresh_button.setEnabled(True)
        self.project_dropdown.clear()
        self.project_dropdown.addItem("Project loading failed")
        self.project_dropdown.setEnabled(False)
        
        # Display the error text
        self.status_label.setStyleSheet("color: #EF4444;")
        self.status_label.setText(error_message)

        # Transition back to login view if token has expired
        if "session expired" in error_message.lower():
            self.unauthorized_error.emit()

    def on_project_changed(self, index: int) -> None:
        """Handler for changes in Project combo box selection."""
        # Index 0 is the default placeholder or loading message
        if index <= 0 or not self.projects_list:
            self.task_dropdown.clear()
            self.task_dropdown.addItem("Select project first")
            self.task_dropdown.setEnabled(False)
            self.status_label.setText("")
            self.tasks_list = []
            self.start_stop_button.setEnabled(False)
            self.timer_engine.reset()
            self.timer_display.setText("00:00:00")
            self.current_time_entry_id = None
            return

        # Get selected project structure (compensate for index 0 offset)
        project = self.projects_list[index - 1]
        project_id = project.get("id")

        if project_id is not None:
            self.trigger_load_tasks(project_id)

    def trigger_load_tasks(self, project_id: int) -> None:
        """Trigger background fetching of nested tasks for selected project."""
        self.status_label.setText("")
        self.start_stop_button.setEnabled(False)
        self.task_dropdown.clear()
        self.task_dropdown.addItem("Loading tasks...")
        self.task_dropdown.setEnabled(False)

        self.tasks_worker = LoadTasksWorker(self.task_service, project_id)
        self.tasks_worker.finished.connect(self.on_tasks_loaded)
        self.tasks_worker.error.connect(self.on_tasks_load_error)
        self.tasks_worker.finished.connect(self.tasks_worker.deleteLater)
        self.tasks_worker.error.connect(self.tasks_worker.deleteLater)
        self.tasks_worker.start()

    def on_tasks_loaded(self, tasks: list) -> None:
        self.task_dropdown.clear()
        self.tasks_list = tasks

        if not tasks:
            self.task_dropdown.addItem("No tasks available")
            self.task_dropdown.setEnabled(False)
            return

        # Add default placeholder selection at index 0
        self.task_dropdown.addItem("[ Select Task ]")
        for task in tasks:
            self.task_dropdown.addItem(task.get("task_name", "Unnamed Task"))
        
        self.task_dropdown.setEnabled(True)

    def on_tasks_load_error(self, error_message: str) -> None:
        self.task_dropdown.clear()
        self.task_dropdown.addItem("Task loading failed")
        self.task_dropdown.setEnabled(False)
        
        self.status_label.setStyleSheet("color: #EF4444;")
        self.status_label.setText(error_message)

        if "session expired" in error_message.lower():
            self.unauthorized_error.emit()

    def on_task_changed(self, index: int) -> None:
        """Handler for changes in Task combo box selection."""
        if index <= 0 or not self.tasks_list:
            self.status_label.setText("")
            self.start_stop_button.setEnabled(False)
            self.timer_engine.reset()
            self.timer_display.setText("00:00:00")
            self.current_time_entry_id = None
            return

        # Enable Start button once project & task exist
        self.start_stop_button.setEnabled(True)
        self.start_stop_button.setText("START")
        self.start_stop_button.setStyleSheet(
            "background-color: #2563EB; color: white; padding: 10px; "
            "border-radius: 4px; font-weight: bold; border: none;"
        )
        self.status_label.setStyleSheet("color: #64748B; font-weight: bold;")
        self.status_label.setText("Ready to start tracking.")
        self.timer_engine.reset()
        self.timer_display.setText("00:00:00")
        self.current_time_entry_id = None

    def toggle_timer(self) -> None:
        """Start or Stop the backend time entry and coordinate local timing engine state."""
        if self.timer_engine.state == TimerState.RUNNING:
            if self.current_time_entry_id is None:
                return

            # Lock stop button during finalize request
            self.start_stop_button.setEnabled(False)
            self.start_stop_button.setText("Stopping...")
            self.status_label.setStyleSheet("color: #64748B;")
            self.status_label.setText("Stopping tracking...")

            self.stop_worker = StopTimeEntryWorker(self.time_entry_service, self.current_time_entry_id)
            self.stop_worker.finished.connect(self.on_stop_success)
            self.stop_worker.error.connect(self.on_stop_error)
            self.stop_worker.finished.connect(self.stop_worker.deleteLater)
            self.stop_worker.error.connect(self.stop_worker.deleteLater)
            self.stop_worker.start()
        else:
            project_idx = self.project_dropdown.currentIndex()
            task_idx = self.task_dropdown.currentIndex()

            if project_idx <= 0 or not self.projects_list:
                self.status_label.setStyleSheet("color: #EF4444;")
                self.status_label.setText("Please select a project.")
                return

            if task_idx <= 0 or not self.tasks_list:
                self.status_label.setStyleSheet("color: #EF4444;")
                self.status_label.setText("Please select a task.")
                return

            project_id = self.projects_list[project_idx - 1].get("id")
            task_id = self.tasks_list[task_idx - 1].get("id")

            if project_id is None or task_id is None:
                return

            # Lock start button and UI dropdowns during creation request
            self.project_dropdown.setEnabled(False)
            self.task_dropdown.setEnabled(False)
            self.refresh_button.setEnabled(False)
            self.logout_button.setEnabled(False)
            
            self.start_stop_button.setEnabled(False)
            self.start_stop_button.setText("Starting...")
            self.status_label.setStyleSheet("color: #64748B;")
            self.status_label.setText("Starting tracking...")

            # Capture targeted IDs for the thread worker
            self.start_worker = StartTimeEntryWorker(self.time_entry_service, project_id, task_id)
            self.start_worker.finished.connect(lambda entry_id: self.on_start_success(entry_id, project_id, task_id))
            self.start_worker.error.connect(self.on_start_error)
            self.start_worker.finished.connect(self.start_worker.deleteLater)
            self.start_worker.error.connect(self.start_worker.deleteLater)
            self.start_worker.start()

    def on_start_success(self, entry_id: int, project_id: int, task_id: int) -> None:
        self.current_time_entry_id = entry_id
        
        # Start local digital timer engine
        self.timer_engine.start(project_id, task_id)
        self.ui_timer.start(100) # update display every 100ms

        # Re-enable toggle button for Stop
        self.start_stop_button.setEnabled(True)
        self.start_stop_button.setText("STOP")
        self.start_stop_button.setStyleSheet(
            "background-color: #EF4444; color: white; padding: 10px; "
            "border-radius: 4px; font-weight: bold; border: none;"
        )
        self.status_label.setStyleSheet("color: #10B981; font-weight: bold;")
        self.status_label.setText("Tracking")

    def on_start_error(self, error_message: str) -> None:
        # Unlock dropdowns since database start operation failed
        self.project_dropdown.setEnabled(True)
        self.task_dropdown.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.logout_button.setEnabled(True)

        self.start_stop_button.setEnabled(True)
        self.start_stop_button.setText("START")
        self.start_stop_button.setStyleSheet(
            "background-color: #2563EB; color: white; padding: 10px; "
            "border-radius: 4px; font-weight: bold; border: none;"
        )
        self.status_label.setStyleSheet("color: #EF4444; font-weight: bold;")
        self.status_label.setText(error_message)

        if "session expired" in error_message.lower():
            self.unauthorized_error.emit()

    def on_stop_success(self, result: dict) -> None:
        # Stop local digital clock
        self.timer_engine.stop()
        self.ui_timer.stop()
        self.update_timer_display()

        # Reset active session ID reference
        self.current_time_entry_id = None

        # Re-enable UI selections
        self.project_dropdown.setEnabled(True)
        self.task_dropdown.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.logout_button.setEnabled(True)

        self.start_stop_button.setEnabled(True)
        self.start_stop_button.setText("START")
        self.start_stop_button.setStyleSheet(
            "background-color: #2563EB; color: white; padding: 10px; "
            "border-radius: 4px; font-weight: bold; border: none;"
        )
        self.status_label.setStyleSheet("color: #EF4444; font-weight: bold;")
        self.status_label.setText("Stopped")

    def on_stop_error(self, error_message: str) -> None:
        # Keep timer running and preserve time_entry_id. Re-enable STOP button.
        self.start_stop_button.setEnabled(True)
        self.start_stop_button.setText("STOP")
        self.start_stop_button.setStyleSheet(
            "background-color: #EF4444; color: white; padding: 10px; "
            "border-radius: 4px; font-weight: bold; border: none;"
        )
        self.status_label.setStyleSheet("color: #EF4444; font-weight: bold;")
        self.status_label.setText(error_message)

        if "session expired" in error_message.lower():
            self.unauthorized_error.emit()

    def update_timer_display(self) -> None:
        """Compute current engine elapsed time and refresh formatted visual digital clocks."""
        total_seconds = int(self.timer_engine.elapsed())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        self.timer_display.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    def reset_state(self) -> None:
        """Clear dropdown selection index, timing engine parameters, and labels."""
        self.ui_timer.stop()
        self.timer_engine.reset()
        self.timer_display.setText("00:00:00")
        self.projects_list = []
        self.tasks_list = []
        self.project_dropdown.clear()
        self.task_dropdown.clear()
        self.status_label.setText("")
        self.start_stop_button.setEnabled(False)
        self.start_stop_button.setText("START")
        self.current_time_entry_id = None

    def handle_logout(self) -> None:
        self.reset_state()
        self.logout_requested.emit()


class MainWindow(QMainWindow):
    """Main window class coordinating widget swapping, close event interception, and dependency injections."""

    def __init__(
        self,
        auth_service: AuthService,
        session_manager: SessionManager,
        project_service: ProjectService,
        task_service: TaskService,
        time_entry_service: TimeEntryService
    ) -> None:
        super().__init__()
        self.auth_service = auth_service
        self.session_manager = session_manager
        self.project_service = project_service
        self.task_service = task_service
        self.time_entry_service = time_entry_service
        
        self.setWindowTitle("SMS Desktop")
        self.resize(450, 450)
        self.init_ui()

    def init_ui(self) -> None:
        self.stacked_widget = QStackedWidget(self)
        self.setCentralWidget(self.stacked_widget)

        self.login_widget = LoginWidget(self.auth_service, self)
        self.dashboard_widget = DashboardPlaceholder(
            self.session_manager,
            self.project_service,
            self.task_service,
            self.time_entry_service,
            self
        )

        self.stacked_widget.addWidget(self.login_widget)
        self.stacked_widget.addWidget(self.dashboard_widget)

        # Wire Signals/Slots
        self.login_widget.login_success.connect(self.show_dashboard)
        self.dashboard_widget.logout_requested.connect(self.show_login)
        self.dashboard_widget.unauthorized_error.connect(self.show_login)

        self.stacked_widget.setCurrentWidget(self.login_widget)

    def show_dashboard(self, user_data: dict) -> None:
        self.dashboard_widget.populate_user_profile()
        self.stacked_widget.setCurrentWidget(self.dashboard_widget)
        # Load user projects automatically upon logging in
        self.dashboard_widget.trigger_load_projects()

    def show_login(self) -> None:
        self.auth_service.logout()
        self.dashboard_widget.reset_state()
        self.stacked_widget.setCurrentWidget(self.login_widget)

    def closeEvent(self, event) -> None:
        """Prevent window close events if the timing engine is currently active."""
        if self.dashboard_widget.timer_engine.state == TimerState.RUNNING:
            QMessageBox.warning(
                self,
                "Timer Running",
                "Timer is currently running. Stop the timer before closing SMS Desktop."
            )
            event.ignore()
        else:
            self.dashboard_widget.ui_timer.stop()
            self.dashboard_widget.timer_engine.reset()
            event.accept()


def main() -> None:
    # Initialize connection dependencies
    api_client = ApiClient()
    session_manager = SessionManager()
    
    # Initialize service layers
    auth_service = AuthService(api_client, session_manager)
    project_service = ProjectService(api_client)
    task_service = TaskService(api_client)
    time_entry_service = TimeEntryService(api_client)

    app = QApplication(sys.argv)
    app.setApplicationName("SMS Desktop")

    window = MainWindow(auth_service, session_manager, project_service, task_service, time_entry_service)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
