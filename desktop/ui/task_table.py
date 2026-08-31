"""
Task table — My Tasks section.

Displays tasks for the selected project with Start/Stop controls.
Supports Add/Edit/Duplicate/Delete and single-active-timer switching.

Ownership: this module is presentation only. It owns no threads, performs no
HTTP calls directly and holds no authoritative timer state. User actions are
expressed as intent through `BackgroundApi`; the TimerService and SyncService
own the state and its durability and publish results back through signals.

Optimistic UI still applies, but it is implemented in the service layer rather
than here: the timer commits locally the instant the user acts and reconciles
with the backend afterwards, so the UI is immediate without the widget having
to guess at, or duplicate, the authoritative state.
"""
from datetime import date, datetime, timezone
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, Signal, QByteArray, QDate, QTime
from PySide6.QtGui import QFont, QColor, QPainter
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QScrollArea, QToolButton,
    QMenu, QMessageBox, QDialog, QTextEdit, QFormLayout,
    QGraphicsDropShadowEffect, QComboBox, QCheckBox, QDateEdit, QTimeEdit,
    QAbstractSpinBox,
)

from app.tasks.service import TaskService
from background_services.public_api import NotificationLevel
from ui import icons
from ui.styles import (
    PRIMARY, PRIMARY_HOVER, SUCCESS, SUCCESS_BG,
    ERROR, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BORDER_LIGHT, CARD_BG, CONTENT_BG, TASK_TABLE_QSS,
    MONITRA_MARK_SVG, BORDER_MID
)


def _fmt_seconds(s: int) -> str:
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _fmt_hours(h: Optional[float]) -> str:
    if h is None:
        return "--"
    total_min = int(h * 60)
    hh = total_min // 60
    mm = total_min % 60
    return f"{hh:02d}:{mm:02d}"


def _pct(tracked: int, budget_hours: Optional[float]) -> Optional[int]:
    if not budget_hours or budget_hours <= 0:
        return None
    pct = int((tracked / (budget_hours * 3600)) * 100)
    return min(pct, 100)


def _fmt_created(created_at: Optional[str]) -> str:
    if not created_at:
        return "--"
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        local_dt = dt.astimezone()
        return local_dt.strftime("%d-%m-%Y %H:%M")
    except Exception:
        return str(created_at)[:16]


# ─── Dialogs ─────────────────────────────────────────────────────────────────

class AddTaskDialog(QDialog):
    def __init__(self, project_name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Task")
        self.setModal(True)
        self.setFixedSize(400, 260)
        self._build_ui(project_name)
        self._apply_style()

    def _build_ui(self, project_name: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        # Compact project display (read-only styled like a dropdown)
        proj_field = QLineEdit(project_name, self)
        proj_field.setReadOnly(True)
        proj_field.setFixedHeight(34)
        proj_field.setObjectName("ProjectReadOnly")
        form.addRow("Project", proj_field)

        self.name_input = QLineEdit(self)
        self.name_input.setPlaceholderText("Enter task name")
        self.name_input.setFixedHeight(34)
        form.addRow("Task Name *", self.name_input)

        self.desc_input = QTextEdit(self)
        self.desc_input.setPlaceholderText("Enter task description (optional)")
        self.desc_input.setFixedHeight(68)
        form.addRow("Description", self.desc_input)

        layout.addLayout(form)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel", self)
        self.cancel_btn.setFixedSize(80, 32)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save", self)
        self.save_btn.setObjectName("SaveBtn")
        self.save_btn.setFixedSize(80, 32)
        self.save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #FFFFFF;
            }}
            QLabel {{
                font-size: 12px;
                font-weight: 600;
                color: #334155;
                background: transparent;
            }}
            QLineEdit, QTextEdit {{
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 10px;
                background-color: #FFFFFF;
                font-size: 13px;
                color: #0F172A;
            }}
            QLineEdit#ProjectReadOnly {{
                background-color: #F8FAFC;
                color: #475569;
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border-color: {PRIMARY};
            }}
            QPushButton {{
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#SaveBtn {{
                background-color: {PRIMARY};
                color: #FFFFFF;
                border: none;
            }}
            QPushButton#SaveBtn:hover {{
                background-color: {PRIMARY_HOVER};
            }}
            QPushButton[text="Cancel"] {{
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                color: #64748B;
            }}
            QPushButton[text="Cancel"]:hover {{
                background-color: #F8FAFC;
            }}
        """)

    def get_data(self) -> dict:
        return {
            "task_name": self.name_input.text().strip(),
            "description": self.desc_input.toPlainText().strip(),
            "estimated_hours": None
        }


class EditTaskDialog(QDialog):
    def __init__(self, task: dict, statuses: list, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Task")
        self.setModal(True)
        self.setFixedSize(380, 310)
        self.estimated_hours = task.get("estimated_hours")
        self._statuses = statuses
        self._build_ui(task)
        self._apply_style()

    def _build_ui(self, task: dict) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.name_input = QLineEdit(self)
        task_name = task.get("name") or task.get("task_name") or ""
        self.name_input.setText(task_name)
        self.name_input.setPlaceholderText("Enter task name")
        self.name_input.setFixedHeight(30)
        form.addRow("Task Name*:", self.name_input)

        self.desc_input = QTextEdit(self)
        orig_desc = task.get("description") or ""
        clean_desc = orig_desc.replace("[duplicate]", "").strip()
        self.desc_input.setPlainText(clean_desc)
        self.desc_input.setPlaceholderText("Enter task description (optional)")
        self.desc_input.setFixedHeight(70)
        form.addRow("Description:", self.desc_input)

        # Status dropdown
        self.status_combo = QComboBox(self)
        self.status_combo.setFixedHeight(30)
        
        current_status_id = None
        task_status = task.get("status")
        if isinstance(task_status, dict):
            current_status_id = task_status.get("id")
            
        selected_index = 0
        for idx, status in enumerate(self._statuses):
            self.status_combo.addItem(status.get("name"), status.get("id"))
            if current_status_id is not None and status.get("id") == current_status_id:
                selected_index = idx
        self.status_combo.setCurrentIndex(selected_index)
        form.addRow("Status:", self.status_combo)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel", self)
        self.cancel_btn.setFixedSize(80, 30)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save", self)
        self.save_btn.setFixedSize(80, 30)
        self.save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #FFFFFF;
            }}
            QLabel {{
                font-size: 12px;
                color: #334155;
                background: transparent;
            }}
            QLineEdit, QTextEdit {{
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 8px;
                background-color: #FFFFFF;
                font-size: 12px;
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border-color: {PRIMARY};
            }}
            QPushButton {{
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
            QPushButton[text="Save"] {{
                background-color: {PRIMARY};
                color: #FFFFFF;
                border: none;
            }}
            QPushButton[text="Cancel"] {{
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                color: #64748B;
            }}
        """)

    def get_data(self) -> dict:
        status_id = self.status_combo.currentData()
        return {
            "task_name": self.name_input.text().strip(),
            "description": self.desc_input.toPlainText().strip(),
            "status_id": status_id,
            "estimated_hours": self.estimated_hours
        }


class DeleteConfirmDialog(QDialog):
    def __init__(self, task_name: str, is_admin: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Delete Task")
        # Frameless dialog — no native black border/frame
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(440, 280)
        self._build_ui(task_name, is_admin)
        self._apply_style()

    def _build_ui(self, task_name: str, is_admin: bool) -> None:
        # Transparent outer layout to support drop shadow
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)

        # White main dialog card container
        self.card = QFrame(self)
        self.card.setObjectName("DialogCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(28, 28, 28, 24)
        card_layout.setSpacing(14)

        # Drop shadow — soft, no black frame
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 45))
        shadow.setOffset(0, 6)
        self.card.setGraphicsEffect(shadow)

        # ── Branding row (logo + wordmark) ────────────────────────
        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        brand_row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.logo_mark = QSvgWidget(self.card)
        self.logo_mark.load(QByteArray(MONITRA_MARK_SVG.encode()))
        self.logo_mark.setFixedSize(44, 44)
        brand_row.addWidget(self.logo_mark)

        wordmark = QLabel("Monitra", self.card)
        wordmark.setObjectName("BrandWordmark")
        wordmark.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        wordmark.setStyleSheet(f"color: {TEXT_PRIMARY}; letter-spacing: -0.5px;")
        brand_row.addWidget(wordmark)
        brand_row.addStretch()

        card_layout.addLayout(brand_row)

        # Thin divider
        divider = QFrame(self.card)
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {BORDER_LIGHT}; border: none;")
        card_layout.addWidget(divider)

        # ── Title + body ──────────────────────────────────────────
        title_label = QLabel("Delete Task?", self.card)
        title_label.setObjectName("DialogTitle")
        title_label.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        title_label.setStyleSheet(f"color: {TEXT_PRIMARY};")
        card_layout.addWidget(title_label)

        if is_admin:
            body_text = (
                f"Are you sure you want to delete <b>{task_name}</b>?<br><br>"
                "Any tracked hours or task-related records associated with this task may be affected. "
                "This action cannot be undone."
            )
        else:
            body_text = f"Are you sure you want to delete <b>{task_name}</b>?"

        body_label = QLabel(body_text, self.card)
        body_label.setObjectName("DialogBody")
        body_label.setFont(QFont("Segoe UI", 11))
        body_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        body_label.setWordWrap(True)
        card_layout.addWidget(body_label)

        # ── Buttons ───────────────────────────────────────────────
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        buttons_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel", self.card)
        self.cancel_btn.setObjectName("SecondaryBtn")
        self.cancel_btn.setFixedSize(80, 34)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_btn)

        delete_btn_text = "Delete Task" if is_admin else "Delete"
        self.delete_btn = QPushButton(delete_btn_text, self.card)
        self.delete_btn.setObjectName("DestructiveBtn")
        self.delete_btn.setFixedSize(90, 34)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(self.delete_btn)

        card_layout.addLayout(buttons_layout)
        outer_layout.addWidget(self.card)

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QFrame#DialogCard {{
                background-color: #FFFFFF;
                border: none;
                border-radius: 14px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QPushButton {{
                border-radius: 7px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#SecondaryBtn {{
                background-color: #FFFFFF;
                border: 1.5px solid {BORDER_LIGHT};
                color: {TEXT_SECONDARY};
            }}
            QPushButton#SecondaryBtn:hover {{
                background-color: #F8FAFC;
                border-color: {BORDER_MID};
                color: {TEXT_PRIMARY};
            }}
            QPushButton#SecondaryBtn:pressed {{
                background-color: #F1F5F9;
            }}
            QPushButton#DestructiveBtn {{
                background-color: {ERROR};
                border: none;
                color: #FFFFFF;
            }}
            QPushButton#DestructiveBtn:hover {{
                background-color: #DC2626;
            }}
            QPushButton#DestructiveBtn:pressed {{
                background-color: #B91C1C;
            }}
        """)


class ManualTimeEntryDialog(QDialog):
    """
    Log time for a project/task after the fact, distinct from the live
    Start/Stop timer.

    Presentation only, matching every other dialog in this file: it owns no
    threads and makes no API calls. Project selection is local (the caller
    already has the full project list); task selection is cascading and
    async, so the owner listens for `project_changed` and calls
    `set_tasks_loading()` / `set_tasks()` once the fetch completes.
    """
    project_changed = Signal(int)

    def __init__(
        self,
        projects: List[Dict[str, Any]],
        initial_project_id: Optional[int] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Manual Time Entry")
        self.setModal(True)
        self.setFixedSize(420, 480)
        self._projects = projects
        self._build_ui()
        self._apply_style()

        if initial_project_id is not None:
            idx = self.project_combo.findData(initial_project_id)
            if idx >= 0:
                self.project_combo.setCurrentIndex(idx)
        # No project_changed emit here: __init__ runs before the caller has
        # had a chance to connect to this signal, so an emit at this point
        # is silently lost -- exactly why the task dropdown never populated
        # when a project was already selected by default. The caller kicks
        # off the initial task load itself, after connecting, once this
        # dialog is constructed.

    def _build_time_field(self, initial_time: QTime) -> "tuple[QWidget, QTimeEdit]":
        """
        A clock-icon-prefixed time field with no visible spin-box arrows --
        the up/down buttons on a plain QTimeEdit were the "clunky" control
        being replaced. Segments (hour/minute/AM-PM) are still editable by
        clicking a segment and typing or scrolling the mouse wheel over it;
        only the built-in increment/decrement buttons are hidden.

        Returns (wrapper_widget_for_the_form, the_actual_QTimeEdit) -- the
        caller keeps using the QTimeEdit directly for .time()/.timeChanged/
        get_data(), only how it's added to the form layout changes.
        """
        wrapper = QFrame(self)
        wrapper.setObjectName("TimeFieldWrapper")
        wrapper.setFixedHeight(34)
        field_layout = QHBoxLayout(wrapper)
        field_layout.setContentsMargins(10, 0, 8, 0)
        field_layout.setSpacing(6)

        icon_label = QLabel(wrapper)
        icon_label.setPixmap(icons.pixmap("timer", TEXT_MUTED, 15))
        field_layout.addWidget(icon_label)

        time_edit = QTimeEdit(initial_time, wrapper)
        time_edit.setObjectName("TimeEditInner")
        time_edit.setDisplayFormat("hh:mm AP")
        time_edit.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        time_edit.setFrame(False)
        field_layout.addWidget(time_edit, 1)

        return wrapper, time_edit

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.project_combo = QComboBox(self)
        self.project_combo.setFixedHeight(34)
        for project in self._projects:
            self.project_combo.addItem(
                project.get("project_name") or project.get("name") or "Unnamed", project.get("id")
            )
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        form.addRow("Project *", self.project_combo)

        self.task_combo = QComboBox(self)
        self.task_combo.setFixedHeight(34)
        self.task_combo.setEnabled(False)
        form.addRow("Task *", self.task_combo)

        today = QDate.currentDate()
        self.date_input = QDateEdit(today, self)
        self.date_input.setCalendarPopup(True)
        self.date_input.setMaximumDate(today)
        self.date_input.setDisplayFormat("MMM d, yyyy")
        self.date_input.setFixedHeight(34)
        form.addRow("Work Date *", self.date_input)

        now = QTime.currentTime()
        start_field, self.start_input = self._build_time_field(QTime(max(0, now.hour() - 1), now.minute()))
        self.start_input.timeChanged.connect(self._update_duration)
        form.addRow("Start Time *", start_field)

        end_field, self.end_input = self._build_time_field(now)
        self.end_input.timeChanged.connect(self._update_duration)
        form.addRow("End Time *", end_field)

        self.duration_label = QLabel("Duration: 1h 0m", self)
        self.duration_label.setObjectName("DurationLabel")
        form.addRow("", self.duration_label)

        self.billable_check = QCheckBox("Billable", self)
        self.billable_check.setChecked(True)
        form.addRow("", self.billable_check)

        self.desc_input = QTextEdit(self)
        self.desc_input.setPlaceholderText("What did you work on? (optional)")
        self.desc_input.setFixedHeight(64)
        form.addRow("Description", self.desc_input)

        layout.addLayout(form)

        self.error_label = QLabel("", self)
        self.error_label.setObjectName("ErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel", self)
        self.cancel_btn.setFixedSize(80, 32)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save Entry", self)
        self.save_btn.setObjectName("SaveBtn")
        self.save_btn.setFixedSize(110, 32)
        self.save_btn.clicked.connect(self._on_save_clicked)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)
        self._update_duration()

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #FFFFFF;
            }}
            QLabel {{
                font-size: 12px;
                font-weight: 600;
                color: #334155;
                background: transparent;
            }}
            QLabel#DurationLabel {{
                color: {PRIMARY};
                font-weight: 700;
            }}
            QLabel#ErrorLabel {{
                color: {ERROR};
                font-weight: 600;
                font-size: 12px;
            }}
            QLineEdit, QTextEdit, QComboBox, QDateEdit {{
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 10px;
                background-color: #FFFFFF;
                font-size: 13px;
                color: #0F172A;
            }}
            QComboBox:disabled, QLineEdit:disabled {{
                background-color: #F8FAFC;
                color: #94A3B8;
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateEdit:focus {{
                border-color: {PRIMARY};
            }}
            QFrame#TimeFieldWrapper {{
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                background-color: #FFFFFF;
            }}
            QTimeEdit#TimeEditInner {{
                border: none;
                background: transparent;
                font-size: 13px;
                color: #0F172A;
            }}
            QPushButton {{
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#SaveBtn {{
                background-color: {PRIMARY};
                color: #FFFFFF;
                border: none;
            }}
            QPushButton#SaveBtn:hover {{
                background-color: {PRIMARY_HOVER};
            }}
            QPushButton#SaveBtn:disabled {{
                background-color: #93C5FD;
            }}
            QPushButton[text="Cancel"] {{
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                color: #64748B;
            }}
            QPushButton[text="Cancel"]:hover {{
                background-color: #F8FAFC;
            }}
        """)

    def _on_project_changed(self, _index: int) -> None:
        self.task_combo.clear()
        self.task_combo.setEnabled(False)
        project_id = self.project_combo.currentData()
        if project_id is not None:
            self.project_changed.emit(project_id)

    def set_tasks_loading(self) -> None:
        self.task_combo.clear()
        self.task_combo.addItem("Loading tasks…", None)
        self.task_combo.setEnabled(False)

    def set_tasks(self, tasks: List[Dict[str, Any]]) -> None:
        self.task_combo.clear()
        for task in tasks:
            name = task.get("name") or task.get("task_name") or "Unnamed"
            self.task_combo.addItem(name, task.get("id"))
        self.task_combo.setEnabled(bool(tasks))
        if not tasks:
            self.task_combo.addItem("No tasks in this project", None)

    def _update_duration(self) -> None:
        start = self.start_input.time()
        end = self.end_input.time()
        seconds = start.secsTo(end)
        if seconds < 0:
            self.duration_label.setText("Duration: —")
            self.duration_label.setStyleSheet(f"color: {ERROR}; font-weight: 700;")
        else:
            hours, rem = divmod(seconds, 3600)
            minutes = rem // 60
            self.duration_label.setText(f"Duration: {hours}h {minutes}m")
            self.duration_label.setStyleSheet(f"color: {PRIMARY}; font-weight: 700;")

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def _on_save_clicked(self) -> None:
        self.error_label.hide()
        if self.project_combo.currentData() is None:
            self._show_error("Select a project.")
            return
        if self.task_combo.currentData() is None:
            self._show_error("Select a task.")
            return
        if self.start_input.time().secsTo(self.end_input.time()) < 0:
            self._show_error("End time cannot be before start time.")
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        """
        Validated form data, with start/end converted from the local
        wall-clock selection to real UTC-aware timestamps (the naive
        QDateEdit/QTimeEdit values represent this machine's local time, not
        UTC, so they're localized before being sent to the backend).
        """
        work_date = self.date_input.date().toPython()
        start_local = datetime.combine(work_date, self.start_input.time().toPython()).astimezone()
        end_local = datetime.combine(work_date, self.end_input.time().toPython()).astimezone()
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = end_local.astimezone(timezone.utc)
        return {
            "project_id": self.project_combo.currentData(),
            "task_id": self.task_combo.currentData(),
            "work_date": work_date.isoformat(),
            "start_time": start_utc.isoformat(),
            "end_time": end_utc.isoformat(),
            "total_seconds": int((end_utc - start_utc).total_seconds()),
            "description": self.desc_input.toPlainText().strip() or None,
            "is_billable": self.billable_check.isChecked(),
        }


# ─── Task Row ─────────────────────────────────────────────────────────────────

class TaskRow(QFrame):
    """
    A single task row widget.

    Presentation only. The row owns no threads, performs no API calls and
    holds no authoritative timer state: it renders whatever the TimerService
    reports and emits intent upwards. Previously each row created its own
    Start/Stop QThread workers and maintained its own `_local_tick` counter,
    which is how the displayed time could disagree with the tracked time.

    Emits: start_requested(row), stop_requested(row), edit_requested(row),
    duplicate_requested(row), delete_requested(row)
    """
    start_requested = Signal(object)
    stop_requested = Signal(object)
    edit_requested = Signal(object)
    duplicate_requested = Signal(object)
    delete_requested = Signal(object)

    timer_started = Signal(int, int)   # task_id, entry_id
    timer_stopped = Signal(int)        # task_id
    error_occurred = Signal(str)
    active_timer_conflict = Signal()

    def __init__(
        self,
        task: Dict[str, Any],
        project_id: int,
        project_name: str,
        project_color: str,
        is_running: bool = False,
        readonly: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.task = task
        self.project_id = project_id
        self.project_name = project_name
        self.project_color = project_color
        self._is_running = is_running
        self._entry_id: Optional[int] = None
        #: Time already banked against this task today, from the backend/cache.
        self._elapsed_seconds = task.get("time_tracked_seconds", 0)
        #: Seconds elapsed in the *current* session, supplied by the
        #: TimerService. The row never increments this itself.
        self._session_elapsed = 0
        #: True while viewing a past date: Start/Stop is hidden for every
        #: task, since a historical day is a read-only view. Set at
        #: construction and kept current afterwards via set_readonly().
        self._readonly = readonly

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setObjectName("TaskRow")
        self._build_ui()
        self._apply_row_style()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 12, 12)
        layout.setSpacing(0)

        task_name = self.task.get("name") or self.task.get("task_name") or "Unnamed Task"
        desc = self.task.get("description") or ""
        estimated = self.task.get("estimated_hours")
        tracked_s = self._elapsed_seconds

        name_col = QVBoxLayout()
        name_col.setSpacing(2)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)

        name_label = QLabel(task_name, self)
        name_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        name_label.setStyleSheet(f"color: {TEXT_PRIMARY};")
        name_label.setWordWrap(False)
        name_row.addWidget(name_label)

        # "Active" pill -- the row's background/border already hint at a
        # running timer, but a label makes it unambiguous at a glance and
        # distinguishes it from e.g. an unrelated selection highlight.
        self._active_badge = QLabel(self)
        self._active_badge.setObjectName("ActiveBadge")
        self._active_badge.setText(f"{icons.img_tag('timer', SUCCESS, 11)} Active")
        self._active_badge.setStyleSheet(
            f"background: {SUCCESS}; color: white; border-radius: 8px; "
            f"padding: 1px 8px; font-size: 10px; font-weight: 700;"
        )
        self._active_badge.setVisible(self._is_running)
        name_row.addWidget(self._active_badge)
        name_row.addStretch()
        name_col.addLayout(name_row)

        if desc:
            clean_desc = desc.replace("[duplicate]", "").strip()
            if clean_desc:
                desc_label = QLabel(clean_desc[:60] + ("…" if len(clean_desc) > 60 else ""), self)
                desc_label.setFont(QFont("Segoe UI", 10))
                desc_label.setStyleSheet("color: #64748B;")
                name_col.addWidget(desc_label)

        name_widget = QWidget(self)
        name_widget.setLayout(name_col)
        name_widget.setMinimumWidth(160)
        layout.addWidget(name_widget, 7)

        created_str = _fmt_created(self.task.get("created_at"))
        created_label = QLabel(created_str, self)
        created_label.setFont(QFont("Courier New", 10))
        created_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        created_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        created_label.setMinimumWidth(120)
        layout.addWidget(created_label, 1)

        tracked_col = QVBoxLayout()
        tracked_col.setSpacing(3)
        tracked_col.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._time_label = QLabel(_fmt_seconds(tracked_s), self)
        self._time_label.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        self._time_label.setStyleSheet(f"color: {TEXT_PRIMARY};")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tracked_col.addWidget(self._time_label)

        pct = _pct(tracked_s, estimated)
        if pct is not None:
            self._pct_label = QLabel(f"{pct}%", self)
            self._pct_label.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
            self._pct_label.setStyleSheet(f"color: {'#F97316' if pct > 90 else PRIMARY};")
            self._pct_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tracked_col.addWidget(self._pct_label)

            self._progress_bar = ProgressBar(pct, self)
            self._progress_bar.setFixedWidth(80)
            tracked_col.addWidget(self._progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)

        tracked_widget = QWidget(self)
        tracked_widget.setLayout(tracked_col)
        tracked_widget.setMinimumWidth(100)
        layout.addWidget(tracked_widget, 2)

        action_col = QHBoxLayout()
        action_col.setSpacing(6)
        action_col.setContentsMargins(8, 0, 0, 0)

        self._timer_btn = QPushButton(self)
        self._timer_btn.setFixedHeight(28)
        self._timer_btn.setFixedWidth(92)
        self._timer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._timer_btn.clicked.connect(self._on_timer_clicked)
        action_col.addWidget(self._timer_btn)

        self._menu_btn = QToolButton(self)
        self._menu_btn.setIcon(icons.icon("more_vert", TEXT_SECONDARY, 18))
        self._menu_btn.setFixedSize(30, 34)
        self._menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._menu_btn.setStyleSheet(f"""
            QToolButton {{
                background: transparent; border: none;
                color: {TEXT_SECONDARY}; font-size: 20px; font-weight: bold; border-radius: 6px;
            }}
            QToolButton:hover {{
                background: {CONTENT_BG}; color: {TEXT_PRIMARY};
            }}
        """)
        self._menu_btn.clicked.connect(self._show_context_menu)
        action_col.addWidget(self._menu_btn)

        action_widget = QWidget(self)
        action_widget.setLayout(action_col)
        action_widget.setMinimumWidth(130)
        layout.addWidget(action_widget, 2)

        self._update_timer_button()
        self._timer_btn.setVisible(not self._readonly)

    def _apply_row_style(self) -> None:
        if self._is_running:
            # A running task breaks from the flat list look on purpose --
            # a bordered, gently lifted card reads as "this one is different"
            # at a glance, rather than just a slightly tinted list row.
            self.setStyleSheet(f"""
                QFrame#TaskRow {{
                    background: {SUCCESS_BG};
                    border: 1.5px solid {SUCCESS};
                    border-radius: 8px;
                }}
            """)
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(18)
            shadow.setXOffset(0)
            shadow.setYOffset(3)
            shadow.setColor(QColor(SUCCESS).lighter(140))
            self.setGraphicsEffect(shadow)
        else:
            self.setGraphicsEffect(None)
            self.setStyleSheet(f"""
                QFrame#TaskRow {{
                    background: {CARD_BG};
                    border: 1.5px solid transparent;
                    border-bottom: 1px solid {BORDER_LIGHT};
                    border-radius: 0px;
                }}
                QFrame#TaskRow:hover {{
                    background: #FAFBFF;
                }}
            """)

    def _update_timer_button(self) -> None:
        self._apply_row_style()
        self._active_badge.setVisible(self._is_running)
        self._time_label.setStyleSheet(
            f"color: {SUCCESS}; font-weight: 900;" if self._is_running else f"color: {TEXT_PRIMARY};"
        )
        if self._is_running:
            self._timer_btn.setText("Stop")
            self._timer_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {ERROR}; color: white;
                    border: none; border-radius: 6px;
                    font-size: 11px; font-weight: bold;
                }}
                QPushButton:hover {{ background: #DC2626; }}
                QPushButton:disabled {{ background: #E2E8F0; color: #94A3B8; }}
            """)
        else:
            self._timer_btn.setText("Start")
            self._timer_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {SUCCESS}; color: white;
                    border: none; border-radius: 6px;
                    font-size: 11px; font-weight: bold;
                }}
                QPushButton:hover {{ background: #16A34A; }}
                QPushButton:disabled {{ background: #E2E8F0; color: #94A3B8; }}
            """)

    def set_readonly(self, readonly: bool) -> None:
        """Show/hide Start/Stop for this row without touching timer state.

        Called when the viewed date changes to/from a past date. A timer
        that is already running keeps running regardless -- this only
        controls whether this row's own button is reachable.
        """
        if readonly == self._readonly:
            return
        self._readonly = readonly
        self._timer_btn.setVisible(not readonly)

    def _on_timer_clicked(self) -> None:
        if self._is_running:
            self.stop_requested.emit(self)
        else:
            self.start_requested.emit(self)

    # ── Presentation (driven by TimerService; the row decides nothing) ─────

    def mark_running(self, entry_id: Optional[int] = None) -> None:
        """Render this row as the actively tracked task."""
        self._is_running = True
        self._entry_id = entry_id
        self._session_elapsed = 0
        self._timer_btn.setEnabled(True)
        self._update_timer_button()

    def mark_stopped(self, banked_seconds: Optional[int] = None) -> None:
        """
        Render this row as stopped.

        :param banked_seconds: Session seconds to fold into the task's running
            total. Supplied by the TimerService, which is the only component
            that knows the authoritative elapsed value.
        """
        self._is_running = False
        self._entry_id = None
        if banked_seconds:
            self._elapsed_seconds += banked_seconds
        self._session_elapsed = 0
        self._timer_btn.setEnabled(True)
        self._update_timer_button()
        self._time_label.setText(_fmt_seconds(self._elapsed_seconds))

    def set_pending(self, label: str) -> None:
        """Show a transient in-progress label without changing timer state."""
        self._timer_btn.setEnabled(False)
        self._timer_btn.setText(label)

    def set_running(self, running: bool, entry_id: Optional[int] = None, elapsed: int = 0) -> None:
        """Set the rendered running state and session elapsed in one call."""
        if running:
            self.mark_running(entry_id)
            self.update_elapsed_seconds(elapsed)
        else:
            self.mark_stopped()

    def update_elapsed_seconds(self, session_elapsed: int) -> None:
        """
        Render the elapsed time reported by the TimerService.

        This is the only path by which the displayed time changes while a
        timer runs. The row does not count seconds of its own, so a UI
        refresh, a rebuild of the row, or a missed tick cannot make the
        displayed value drift from the tracked value.
        """
        self._session_elapsed = session_elapsed
        self._time_label.setText(_fmt_seconds(self._elapsed_seconds + session_elapsed))

    def set_banked_seconds(self, seconds: int) -> None:
        """Update the task's already-tracked total (e.g. after a refresh)."""
        self._elapsed_seconds = seconds
        self._time_label.setText(
            _fmt_seconds(self._elapsed_seconds + (self._session_elapsed if self._is_running else 0))
        )

    def _show_context_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: white; border: 1px solid {BORDER_LIGHT};
                border-radius: 10px; padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 18px; border-radius: 6px;
                color: {TEXT_PRIMARY}; font-size: 13px;
            }}
            QMenu::item:selected {{ background: {CONTENT_BG}; }}
            QMenu::separator {{
                height: 1px;
                background: {BORDER_LIGHT};
                margin: 4px 10px;
            }}
        """)
        edit_action = menu.addAction(icons.icon("edit", TEXT_PRIMARY), "Edit")
        dup_action = menu.addAction(icons.icon("content_copy", TEXT_PRIMARY), "Duplicate")
        menu.addSeparator()
        del_action = menu.addAction(icons.icon("delete", ERROR), "Delete")
        # Style the delete action text red
        del_action.setProperty("class", "destructive")
        del_widget = menu.widgetForAction(del_action) if hasattr(menu, 'widgetForAction') else None
        pos = self._menu_btn.mapToGlobal(self._menu_btn.rect().bottomLeft())
        selected = menu.exec(pos)
        if selected == edit_action: self.edit_requested.emit(self)
        elif selected == dup_action: self.duplicate_requested.emit(self)
        elif selected == del_action: self.delete_requested.emit(self)


# ─── Progress Bar ─────────────────────────────────────────────────────────────

class ProgressBar(QWidget):
    def __init__(self, percent: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._pct = max(0, min(100, percent))
        self.setFixedHeight(4)
        self.setMinimumWidth(80)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        painter.setBrush(QColor("#E2E8F0"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, w, 4, 2, 2)
        fill_w = int(w * self._pct / 100)
        if fill_w > 0:
            color = "#F97316" if self._pct > 90 else PRIMARY
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(0, 0, fill_w, 4, 2, 2)
        painter.end()


# ─── Task Table Section ───────────────────────────────────────────────────────

class TaskSection(QWidget):
    """
    Full My Tasks section: header, search, task rows.
    Manages the single-timer-at-a-time rule and CRUD operations.
    Emits timer_state_changed(is_active) for sidebar total-time updates.
    """
    timer_state_changed = Signal(bool)   # True = timer started, False = stopped
    error_occurred = Signal(str)
    active_timer_conflict = Signal()
    task_action_succeeded = Signal(str)  # Success notification message
    refresh_requested = Signal()

    def __init__(
        self,
        api,
        task_service: TaskService,
        time_entry_service=None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """
        :param api: `background_services.public_api.BackgroundApi`. The only
            channel through which this widget reaches background work. It owns
            no threads and holds no timer state of its own.
        :param time_entry_service: `app.time_entries.service.TimeEntryService`.
            Optional so existing construction sites without it keep working;
            required in practice for the manual-time-entry Save action.
        """
        super().__init__(parent)
        self.api = api
        self.task_service = task_service
        self.time_entry_service = time_entry_service
        self._tasks: List[Dict[str, Any]] = []
        self._project: Optional[Dict[str, Any]] = None
        self._project_color = "#3B82F6"
        self._task_rows: List[TaskRow] = []
        # Mirrors of the TimerService's state, kept only for rendering.
        self._running_task_id: Optional[int] = None
        self._running_entry_id: Optional[int] = None
        self._running_task_name: Optional[str] = None
        self._user_id: Optional[int] = None
        self._search_text = ""
        self.user_role = None
        self._has_loaded_tasks = False
        #: True while the top bar's selected date is before today. Read-only
        #: view of history: Start/Stop is hidden on every row regardless of
        #: whether a timer happens to be running elsewhere.
        self._viewing_past_date = False
        #: Every project the user can see, for the manual-entry dialog's
        #: project dropdown -- distinct from self._tasks/self._project, which
        #: only ever cover the one project currently displayed.
        self._all_projects: List[Dict[str, Any]] = []
        self._manual_entry_dialog: Optional["ManualTimeEntryDialog"] = None

        # Subscribe to the authoritative timer. No local tick timer exists:
        # elapsed time is published by the service, never counted here.
        timer = self.api.timer
        timer.timer_started.connect(self._on_timer_started)
        timer.timer_stopped.connect(self._on_timer_stopped)
        timer.timer_tick.connect(self._on_timer_tick)
        timer.timer_error.connect(self._on_timer_error)
        self.api.sync.action_failed.connect(self._on_sync_action_failed)

        self._build_ui()

    @property
    def _local_cache(self):
        """Read-only repository access for cached lookups (e.g. task statuses)."""
        return self.api.cache

    def set_user_role(self, role_name: str) -> None:
        self.user_role = role_name

    def set_user_id(self, user_id: int) -> None:
        self._user_id = user_id

    def set_all_projects(self, projects: List[Dict[str, Any]]) -> None:
        """Every project the user can see, for the manual-entry dialog's
        project dropdown. Called by DashboardWindow whenever its own project
        list changes -- this section otherwise only knows the one project
        currently displayed."""
        self._all_projects = projects or []

    @property
    def is_admin(self) -> bool:
        return self.user_role in ["admin", "org_admin", "super_admin"]

    def _run_task_mutation(self, call, success_message: str, key: str) -> None:
        """
        Run a task CRUD call on the shared bounded pool.

        `key` de-duplicates: a double-click cannot produce two creates. On
        success the list is refreshed so the change is reflected without the
        widget guessing at what the server did.
        """
        def on_success(_result) -> None:
            self.api.notify(success_message, NotificationLevel.SUCCESS, key=f"task-mut-{key}")
            self.task_action_succeeded.emit(success_message)
            self.refresh_requested.emit()

        def on_error(exc: BaseException) -> None:
            self.api.notify(str(exc), NotificationLevel.ERROR, key=f"task-mut-err-{key}")
            self.error_occurred.emit(str(exc))

        self.api.run_in_background(call, on_success=on_success, on_error=on_error, key=key)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Card container ─────────────────────────────────────────
        card = QFrame(self)
        card.setObjectName("TaskCard")
        card.setStyleSheet(f"""
            QFrame#TaskCard {{
                background: {CARD_BG};
                border-radius: 12px;
                border: 1px solid {BORDER_LIGHT};
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # ── Header row ─────────────────────────────────────────────
        header_row = QWidget(card)
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(20, 14, 16, 14)
        header_layout.setSpacing(10)

        # Title and Count Row in a vertical layout
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(4)
        title_vbox.setContentsMargins(0, 0, 0, 0)

        title_hbox = QHBoxLayout()
        title_hbox.setSpacing(10)
        title_hbox.setContentsMargins(0, 0, 0, 0)

        # Task count lives right in the title text ("Project Name (10)")
        # rather than a separate badge widget -- keeps the count visually
        # attached to the name it describes instead of floating off to the
        # side of it.
        self._title_label = QLabel("My Tasks", header_row)
        self._title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.ExtraBold))
        self._title_label.setStyleSheet(f"color: {TEXT_PRIMARY};")
        title_hbox.addWidget(self._title_label)

        title_vbox.addLayout(title_hbox)

        self._current_task_lbl = QLabel("No task currently running", header_row)
        self._current_task_lbl.setFont(QFont("Segoe UI", 11))
        self._current_task_lbl.setStyleSheet(
            "color: #64748B; background: #F1F5F9; border: 1px dashed #CBD5E1; "
            "border-radius: 6px; padding: 6px 12px; margin-top: 6px;"
        )
        title_vbox.addWidget(self._current_task_lbl)

        header_layout.addLayout(title_vbox)
        header_layout.addStretch()

        # Search field
        self._search = QLineEdit(header_row)
        self._search.setObjectName("TaskSearch")
        self._search.setPlaceholderText("Search tasks...")
        self._search.setFixedSize(220, 34)
        self._search.setClearButtonEnabled(True)
        icons.line_edit_icon_action(self._search, "search", TEXT_MUTED)
        self._search.textChanged.connect(self._on_search_changed)
        header_layout.addWidget(self._search)

        # Add Task button
        self._add_task_btn = QPushButton(" Add Task", header_row)
        self._add_task_btn.setIcon(icons.icon("add", "#FFFFFF", 16))
        self._add_task_btn.setObjectName("AddTaskBtn")
        self._add_task_btn.setFixedSize(110, 32)
        self._add_task_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_task_btn.setEnabled(False)
        self._add_task_btn.clicked.connect(self._on_add_task_clicked)
        header_layout.addWidget(self._add_task_btn)

        # Manual time entry button
        self._manual_entry_btn = QPushButton(" Log Time", header_row)
        self._manual_entry_btn.setIcon(icons.icon("timer", TEXT_PRIMARY, 15))
        self._manual_entry_btn.setObjectName("ManualEntryBtn")
        self._manual_entry_btn.setFixedSize(110, 32)
        self._manual_entry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._manual_entry_btn.setToolTip("Add a manual time entry for a past date")
        self._manual_entry_btn.setStyleSheet(f"""
            QPushButton#ManualEntryBtn {{
                background: white; border: 1px solid {BORDER_LIGHT}; border-radius: 6px;
                color: {TEXT_PRIMARY}; font-weight: bold;
            }}
            QPushButton#ManualEntryBtn:hover {{
                background: {CONTENT_BG}; border-color: {TEXT_MUTED};
            }}
        """)
        self._manual_entry_btn.clicked.connect(self._on_manual_entry_clicked)
        header_layout.addWidget(self._manual_entry_btn)

        # Refresh button
        self._refresh_btn = QPushButton(" Refresh", header_row)
        self._refresh_btn.setIcon(icons.icon("refresh", TEXT_PRIMARY, 15))
        self._refresh_btn.setObjectName("RefreshBtn")
        self._refresh_btn.setFixedSize(85, 32)
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.setStyleSheet(f"""
            QPushButton#RefreshBtn {{
                background: white; border: 1px solid {BORDER_LIGHT}; border-radius: 6px;
                color: {TEXT_PRIMARY}; font-weight: bold;
            }}
            QPushButton#RefreshBtn:hover {{
                background: {CONTENT_BG}; border-color: {TEXT_MUTED};
            }}
        """)
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)
        header_layout.addWidget(self._refresh_btn)

        card_layout.addWidget(header_row)

        # Divider
        div = QFrame(card)
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {BORDER_LIGHT};")
        card_layout.addWidget(div)

        # ── Column headers ─────────────────────────────────────────
        col_header = QWidget(card)
        col_header.setFixedHeight(38)
        col_header.setStyleSheet(f"background: #F8FAFC; border-bottom: 1px solid {BORDER_LIGHT};")
        col_layout = QHBoxLayout(col_header)
        col_layout.setContentsMargins(16, 0, 12, 0)

        def make_col_header(text: str, stretch: int, min_width: int = 0) -> None:
            lbl = QLabel(text, col_header)
            lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; letter-spacing: 0.8px;")
            if text in ["CREATED", "TRACKED TIME", "BUDGET"]:
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if min_width > 0:
                lbl.setMinimumWidth(min_width)
            if text == "ACTION":
                lbl.setContentsMargins(8, 0, 0, 0)
            col_layout.addWidget(lbl, stretch)

        make_col_header("TASK", 7, 160)
        make_col_header("CREATED", 1, 120)
        make_col_header("TRACKED TIME", 2, 100)
        make_col_header("ACTION", 2, 130)

        card_layout.addWidget(col_header)

        # ── Scrollable task list ───────────────────────────────────
        self._scroll = QScrollArea(card)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._rows_container = QWidget()
        self._rows_container.setStyleSheet(f"background: {CARD_BG};")
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.addStretch()

        self._scroll.setWidget(self._rows_container)
        card_layout.addWidget(self._scroll)

        # Status / empty / loading label
        self._status_label = QLabel("Select a project to see tasks.", self)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(f"color: {TEXT_MUTED}; padding: 40px; font-size: 13px;")
        self._rows_layout.insertWidget(0, self._status_label)

        layout.addWidget(card)

        # Apply specific AddTaskBtn Stylesheet
        self.setStyleSheet(TASK_TABLE_QSS + f"""
            QPushButton#AddTaskBtn {{
                background-color: {PRIMARY};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton#AddTaskBtn:hover {{
                background-color: {PRIMARY_HOVER};
            }}
            QPushButton#AddTaskBtn:pressed {{
                background-color: #1D4ED8;
            }}
            QPushButton#AddTaskBtn:disabled {{
                background-color: #93C5FD;
            }}
        """)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_loading(self, project_name: str) -> None:
        """Show loading state."""
        self._clear_rows()
        self._status_label.setText(f"Loading tasks for {project_name}...")
        self._status_label.show()
        self._title_label.setText(f"{project_name} (…)")
        self._has_loaded_tasks = False

    def set_tasks(
        self,
        tasks: List[Dict[str, Any]],
        project: Dict[str, Any],
        color: str,
    ) -> None:
        """Populate rows from real API task data."""
        self._tasks = tasks or []
        self._project = project
        self._project_color = color
        self._search_text = ""
        self._search.clear()
        self._add_task_btn.setEnabled(True)

        # _rebuild_rows() sets the title (name + task count) below -- no
        # need to set it here too and have it immediately overwritten.
        self._rebuild_rows()
        self._update_current_task_indicator()
        self._has_loaded_tasks = True

    def update_tasks_tracked_times(self, task_time_map: dict) -> None:
        """Update tasks list and rows with today's accumulated tracked times."""
        # 1. Update master tasks list
        for t in self._tasks:
            tid = t.get("id")
            if tid in task_time_map:
                t["time_tracked_seconds"] = task_time_map[tid]
            else:
                t["time_tracked_seconds"] = 0

        # 2. Update visible TaskRow widgets
        for row in self._task_rows:
            tid = row.task.get("id")
            base_elapsed = task_time_map.get(tid, 0)
            row._elapsed_seconds = base_elapsed
            if row._is_running:
                row._time_label.setText(_fmt_seconds(base_elapsed + getattr(row, "_session_elapsed", 0)))
            else:
                row._time_label.setText(_fmt_seconds(base_elapsed))

    def set_error(self, message: str) -> None:
        self._clear_rows()
        self._status_label.setText(f"{icons.img_tag('warning', ERROR)} {message}")
        self._status_label.show()
        self._has_loaded_tasks = False

    def clear(self) -> None:
        self._clear_rows()
        self._status_label.setText("Select a project to see tasks.")
        self._status_label.show()
        self._title_label.setText("My Tasks")
        self._add_task_btn.setEnabled(False)
        self._tasks = []
        self._project = None
        self._update_current_task_indicator()
        self._has_loaded_tasks = False

    def apply_search(self, text: str) -> None:
        """Filters My Tasks search bar."""
        self._search.setText(text)

    def set_viewing_date(self, target_date) -> None:
        """Called whenever the top bar's selected date changes.

        A past date is a read-only view of history: Start/Stop is hidden on
        every row. Today keeps the normal, unchanged behavior. Rows already
        on screen are updated in place; new rows built afterwards (search,
        project switch) pick up the current value from self._viewing_past_date.
        """
        readonly = target_date < date.today()
        if readonly == self._viewing_past_date:
            return
        self._viewing_past_date = readonly
        for row in self._task_rows:
            row.set_readonly(readonly)

    def sync_active_timer(self, task_id: int, entry_id: int, elapsed: int = 0) -> None:
        """
        Render an already-running timer (e.g. after tasks load for a project
        whose task is being tracked).

        Purely presentational — it does not start, stop or re-anchor anything.
        The elapsed value is read from the service rather than the caller's
        argument when a session is live, so a stale argument cannot make the
        displayed time regress.
        """
        self._running_task_id = task_id
        self._running_entry_id = entry_id
        live_elapsed = self.api.timer_elapsed_seconds() if self.api.is_timer_running() else elapsed
        for row in self._task_rows:
            if row.task.get("id") == task_id:
                row.set_running(True, entry_id, live_elapsed)
            else:
                row.set_running(False)
        self.timer_state_changed.emit(True)
        self._update_current_task_indicator()

    # ── Private helpers ────────────────────────────────────────────────────────

    def _update_current_task_indicator(self) -> None:
        if self._running_task_id is not None:
            # Find task in self._tasks
            task = next((t for t in self._tasks if t.get("id") == self._running_task_id), None)
            if task:
                task_name = task.get("name") or task.get("task_name") or "Unknown"
            else:
                # The tracked task may belong to a project that is not the one
                # currently displayed; fall back to the service's own record.
                session = self.api.active_session() or {}
                task_name = (
                    session.get("task_name")
                    if session.get("task_id") == self._running_task_id
                    else None
                ) or self._running_task_name or "Unknown"

            self._current_task_lbl.setText(f"Current: <b>{task_name}</b>")
            self._current_task_lbl.setStyleSheet(
                "color: #1E3A8A; background: #DBEAFE; border: 1.5px solid #3B82F6; "
                "border-radius: 6px; padding: 6px 12px; font-weight: 500; margin-top: 6px;"
            )
            self._current_task_lbl.show()
            return
        
        # Idle state
        self._current_task_lbl.setText("No task currently running")
        self._current_task_lbl.setStyleSheet(
            "color: #64748B; background: #F1F5F9; border: 1px dashed #CBD5E1; "
            "border-radius: 6px; padding: 6px 12px; margin-top: 6px;"
        )
        self._current_task_lbl.show()

    def _rebuild_rows(self) -> None:
        self._clear_rows()

        filtered = [
            t for t in self._tasks
            if self._search_text.lower() in (t.get("name") or t.get("task_name") or "").lower()
        ]

        if self._project:
            project_name = self._project.get("project_name", "Project")
            self._title_label.setText(f"{project_name} ({len(filtered)})")
        else:
            project_name = "Project"
            self._title_label.setText("My Tasks")

        if not filtered:
            msg = "No tasks match your search." if self._search_text else "No tasks found for this project."
            self._status_label.setText(msg)
            self._status_label.show()
            return

        self._status_label.hide()

        for i, task in enumerate(filtered):
            color = self._project_color
            row = TaskRow(
                task=task,
                project_id=self._project.get("id", 0) if self._project else 0,
                project_name=project_name,
                project_color=color,
                is_running=(task.get("id") == self._running_task_id),
                readonly=self._viewing_past_date,
                parent=self._rows_container,
            )
            if task.get("id") == self._running_task_id:
                # Re-read the live value from the service rather than a cached
                # mirror, so a rebuilt row shows the true elapsed time.
                row.set_running(
                    True, self._running_entry_id, self.api.timer_elapsed_seconds()
                )

            row.start_requested.connect(self._handle_start_request)
            row.stop_requested.connect(self._handle_stop_request)
            row.edit_requested.connect(self._handle_edit_request)
            row.duplicate_requested.connect(self._handle_duplicate_request)
            row.delete_requested.connect(self._handle_delete_request)
            row.error_occurred.connect(self.error_occurred)

            self._rows_layout.insertWidget(self._rows_layout.count() - 1, row)
            self._task_rows.append(row)

    def _clear_rows(self) -> None:
        for row in self._task_rows:
            self._rows_layout.removeWidget(row)
            row.deleteLater()
        self._task_rows.clear()

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text
        self._rebuild_rows()

    # ── Timer workflow ────────────────────────────────────────────────────────
    #
    # There is exactly one path here. The audited version carried three
    # competing implementations side by side — a TrackingManager path, a
    # SyncQueue "optimistic" path that reached into `sync_queue._cache` to
    # enqueue rows itself, and a "legacy" path that spawned QThread workers
    # from the widget — selected by whichever collaborator happened to be
    # injected. They maintained separate notions of the running task, the
    # entry id and the elapsed seconds, which is how the UI could disagree
    # with the cache and with the backend simultaneously.
    #
    # All three are gone. This widget expresses intent; TimerService owns the
    # state and the durability, and publishes it back through signals.

    def _handle_start_request(self, row: TaskRow) -> None:
        # The button that emits this is hidden while viewing a past date;
        # this is defense in depth against a stray/queued signal.
        if self._viewing_past_date:
            return
        task_id = row.task.get("id")
        if task_id is None:
            return
        task_name = row.task.get("name") or row.task.get("task_name") or "Unnamed Task"
        row.set_pending("Starting…")
        # switch() handles both "nothing running" and "something else running";
        # the service serialises stop-then-start so the two can never race.
        self.api.switch_timer(row.project_id, task_id, task_name)

    def _handle_stop_request(self, row: TaskRow) -> None:
        if self._viewing_past_date:
            return
        row.set_pending("Stopping…")
        self.api.stop_timer()

    # ── TimerService subscriptions ────────────────────────────────────────────

    def _on_timer_started(self, session: dict) -> None:
        """The authoritative timer began (or was recovered/adopted)."""
        task_id = session.get("task_id")
        entry_id = session.get("entry_id")
        task_name = session.get("task_name") or "Task"
        self._running_task_id = task_id
        self._running_entry_id = entry_id
        self._running_task_name = task_name

        for row in self._task_rows:
            if row.task.get("id") == task_id:
                row.mark_running(entry_id)
            elif row._is_running:
                row.mark_stopped()

        self.timer_state_changed.emit(True)
        self._update_current_task_indicator()
        self._on_timer_tick(self.api.timer_elapsed_seconds())
        self.api.notify(f"Timer started for '{task_name}'", NotificationLevel.SUCCESS, key=f"timer-started-{task_id}")

    def _on_timer_stopped(self, payload: dict) -> None:
        """
        The authoritative timer stopped.
        """
        session = payload.get("session") or {}
        task_id = session.get("task_id")
        elapsed = payload.get("elapsed_seconds", 0)

        for row in self._task_rows:
            if row.task.get("id") == task_id:
                row.mark_stopped(banked_seconds=elapsed)
            elif row._is_running:
                row.mark_stopped()

        if self._running_task_id == task_id:
            self._running_task_id = None
            self._running_entry_id = None
            self._running_task_name = None

        self.timer_state_changed.emit(False)
        self._update_current_task_indicator()
        self.api.notify("Timer stopped. Time entry saved.", NotificationLevel.INFO, key=f"timer-stopped-{task_id}")

    def _on_timer_tick(self, elapsed: int) -> None:
        """
        Render the elapsed seconds reported by the service.

        Skipped while viewing a past date: that row's base is the historical
        completed-hours total for the viewed date (set by
        update_tasks_tracked_times), and folding today's live `elapsed` onto
        it would mix the two. The row keeps showing its completed total,
        unticking, until the user navigates back to today.
        """
        if self._running_task_id is None or self._viewing_past_date:
            return
        for row in self._task_rows:
            if row.task.get("id") == self._running_task_id:
                row.update_elapsed_seconds(elapsed)
                break

    def _on_timer_error(self, message: str) -> None:
        for row in self._task_rows:
            row.set_running(row.task.get("id") == self._running_task_id,
                            self._running_entry_id)
        self.api.notify(f"Timer error: {message}", NotificationLevel.ERROR, key="timer-error")
        self.error_occurred.emit(message)

    # ── Sync feedback ─────────────────────────────────────────────────────────

    def _on_sync_action_failed(self, action_id: str, action_type: str,
                               error: str, will_retry: bool) -> None:
        """
        Surface a durable-sync failure without corrupting local state.

        A failed API call must not reset valid local state: the user's action
        already happened and is recorded durably. Only a permanent failure of
        a timer operation is worth telling the user about, and even then the
        local timer keeps its own truth.
        """
        if will_retry:
            return
        if action_type in ("start_timer", "stop_timer", "switch_timer"):
            self.error_occurred.emit(
                "Could not sync your timer to the server yet. "
                "It is saved locally and will retry automatically."
            )

    # ── Task CRUD operations ──────────────────────────────────────────────────

    def _on_add_task_clicked(self) -> None:
        if not self._project:
            return
        proj_name = self._project.get("project_name", "Project")
        dialog = AddTaskDialog(proj_name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["task_name"]:
                QMessageBox.warning(self, "Validation Error", "Task Name is required.")
                return

            assignee_id = self._user_id or 1
            project_id = self._project.get("id")
            self._run_task_mutation(
                lambda: self.task_service.create_task(
                    project_id, data["task_name"], assignee_id
                ),
                success_message="Task created successfully.",
                key=f"create-task:{project_id}:{data['task_name']}",
            )

    # ── Manual time entry ─────────────────────────────────────────────────────
    #
    # Distinct from the live Start/Stop timer above: this logs a completed
    # session after the fact, through the backend's existing manual-entry
    # endpoint (the same one TimerService's own overlap checking guards
    # against), never the timer's own start/stop path.

    def _on_manual_entry_clicked(self) -> None:
        if not self._all_projects:
            QMessageBox.information(
                self, "No Projects",
                "No projects are available yet. Try again once projects have loaded."
            )
            return
        initial_project_id = self._project.get("id") if self._project else None
        dialog = ManualTimeEntryDialog(self._all_projects, initial_project_id, self)
        self._manual_entry_dialog = dialog
        dialog.project_changed.connect(self._on_manual_entry_project_changed)
        # Load tasks for whichever project ends up selected when the dialog
        # opens -- whether that came from initial_project_id or just the
        # combo box's own default first item -- now that something is
        # actually listening for it.
        if dialog.project_combo.currentData() is not None:
            self._on_manual_entry_project_changed(dialog.project_combo.currentData())

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._submit_manual_entry(dialog.get_data())
        self._manual_entry_dialog = None

    def _on_manual_entry_project_changed(self, project_id: int) -> None:
        dialog = self._manual_entry_dialog
        if dialog is None:
            return
        dialog.set_tasks_loading()

        def on_success(tasks: list) -> None:
            if self._manual_entry_dialog is dialog:
                dialog.set_tasks(tasks)

        def on_error(exc: BaseException) -> None:
            if self._manual_entry_dialog is dialog:
                dialog.set_tasks([])

        self.api.run_in_background(
            lambda: self.task_service.get_tasks_for_project(project_id),
            on_success=on_success,
            on_error=on_error,
            key=f"manual-entry-tasks:{project_id}",
        )

    def _submit_manual_entry(self, data: Dict[str, Any]) -> None:
        if self.time_entry_service is None:
            self.api.notify(
                "Manual time entry is unavailable right now.",
                NotificationLevel.ERROR, key="manual-entry-unavailable",
            )
            return

        def on_success(_result) -> None:
            message = "Manual time entry submitted for approval."
            self.api.notify(message, NotificationLevel.SUCCESS, key="manual-entry-created")
            self.task_action_succeeded.emit(message)

        def on_error(exc: BaseException) -> None:
            message = getattr(exc, "message", None) or str(exc)
            self.api.notify(message, NotificationLevel.ERROR, key="manual-entry-error")
            self.error_occurred.emit(message)

        self.api.run_in_background(
            lambda: self.time_entry_service.create_manual_time_entry(**data),
            on_success=on_success,
            on_error=on_error,
            key=f"manual-entry-create:{data['project_id']}:{data['task_id']}:{data['start_time']}",
        )

    def _handle_edit_request(self, row: TaskRow) -> None:
        statuses = []
        if self._local_cache:
            statuses = self._local_cache.get_cached_task_statuses() or []
        dialog = EditTaskDialog(row.task, statuses, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["task_name"]:
                QMessageBox.warning(self, "Validation Error", "Task Name is required.")
                return

            task_id = row.task.get("id")
            self._run_task_mutation(
                lambda: self.task_service.update_task(
                    row.project_id, task_id, data["task_name"], data["status_id"]
                ),
                success_message="Task updated successfully.",
                key=f"update-task:{task_id}",
            )

    def _handle_duplicate_request(self, row: TaskRow) -> None:
        orig_name = row.task.get("name") or row.task.get("task_name") or "Task"
        orig_desc = row.task.get("description") or ""
        new_desc = orig_desc
        if "[duplicate]" not in orig_desc:
            new_desc = f"{orig_desc}\n[duplicate]".strip()

        assignee_id = row.task.get("assignee_id") or 1
        self._run_task_mutation(
            lambda: self.task_service.create_task(
                row.project_id, f"{orig_name} (Copy)", assignee_id
            ),
            success_message="Task duplicated successfully.",
            key=f"duplicate-task:{row.task.get('id')}",
        )

    def _handle_delete_request(self, row: TaskRow) -> None:
        task_name = row.task.get("name") or row.task.get("task_name") or "Task"
        dialog = DeleteConfirmDialog(task_name, is_admin=self.is_admin, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            task_id = row.task.get("id")
            self._run_task_mutation(
                lambda: self.task_service.delete_task(row.project_id, task_id),
                success_message="Task deleted successfully.",
                key=f"delete-task:{task_id}",
            )

