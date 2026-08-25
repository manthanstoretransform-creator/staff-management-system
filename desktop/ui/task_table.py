"""
Task table — My Tasks section with real backend data.
Displays tasks for the selected project with Start/Stop timer buttons.
Supports Add/Edit/Duplicate/Delete tasks and single-active-timer switching.

Optimistic UI: All user actions update the UI instantly (<50ms), then
push the corresponding API operation to the SyncQueue for background
processing. On server confirmation, entry_id and elapsed time are
reconciled. On failure, the UI reverts with an error notification.
"""
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, Signal, QTimer, QSize, QByteArray
from PySide6.QtGui import QFont, QColor, QPainter
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QScrollArea, QSizePolicy, QToolButton,
    QMenu, QMessageBox, QDialog, QTextEdit, QDoubleSpinBox, QFormLayout,
    QGraphicsDropShadowEffect, QComboBox
)

from app.timer.engine import TimerEngine, TimerState
from app.time_entries.service import TimeEntryService
from app.tasks.service import TaskService
from ui.workers import (
    StartTimeEntryWorker, StopTimeEntryWorker,
    CreateTaskWorker, UpdateTaskWorker, DeleteTaskWorker
)
from ui.styles import (
    PRIMARY, PRIMARY_HOVER, PRIMARY_LIGHT, SUCCESS, SUCCESS_BG,
    ERROR, ERROR_BG, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BORDER_LIGHT, CARD_BG, CONTENT_BG, PROJECT_COLORS, TASK_TABLE_QSS,
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


# ─── Task Row ─────────────────────────────────────────────────────────────────

class TaskRow(QFrame):
    """
    A single task row widget.
    Start/Stop buttons call real TimeEntryService via QThread workers.
    Emits: start_requested(row), stop_requested(row), edit_requested(row), duplicate_requested(row), delete_requested(row)
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
        time_entry_service: TimeEntryService,
        is_running: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.task = task
        self.project_id = project_id
        self.project_name = project_name
        self.project_color = project_color
        self.time_entry_service = time_entry_service
        self._is_running = is_running
        self._entry_id: Optional[int] = None
        self._elapsed_seconds = task.get("time_tracked_seconds", 0)
        self._local_tick = 0
        self._pending_action_id: Optional[str] = None  # Tracks SyncQueue action

        self._start_worker: Optional[StartTimeEntryWorker] = None
        self._stop_worker: Optional[StopTimeEntryWorker] = None
        self._running_workers = set()

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

        name_label = QLabel(task_name, self)
        name_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        name_label.setStyleSheet(f"color: {TEXT_PRIMARY};")
        name_label.setWordWrap(False)
        name_col.addWidget(name_label)

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
        self._menu_btn.setText("⋮")
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

    def _apply_row_style(self) -> None:
        if self._is_running:
            self.setStyleSheet(f"""
                QFrame#TaskRow {{
                    background: {SUCCESS_BG};
                    border-left: 4px solid {SUCCESS};
                    border-bottom: 1px solid {BORDER_LIGHT};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame#TaskRow {{
                    background: {CARD_BG};
                    border-left: 4px solid transparent;
                    border-bottom: 1px solid {BORDER_LIGHT};
                }}
                QFrame#TaskRow:hover {{
                    background: #FAFBFF;
                }}
            """)

    def _update_timer_button(self) -> None:
        self._apply_row_style()
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

    def _on_timer_clicked(self) -> None:
        if self._is_running:
            self.stop_requested.emit(self)
        else:
            self.start_requested.emit(self)

    def _start_worker_thread(self, worker) -> None:
        self._running_workers.add(worker)
        worker.finished.connect(lambda: self._running_workers.discard(worker))
        worker.error.connect(lambda: self._running_workers.discard(worker))
        worker.start()

    # ── Optimistic Start (instant UI, background sync) ────────────────────

    def _do_start_optimistic(self) -> None:
        """Instantly update UI to running state, then queue API call."""
        task_id = self.task.get("id")
        if task_id is None:
            return
        # INSTANT: update UI to running state
        self._is_running = True
        self._local_tick = 0
        self._entry_id = None  # Will be set when server responds
        self._update_timer_button()
        self.timer_started.emit(task_id, -1)  # -1 = pending server confirmation

    def _do_start(self) -> None:
        """Fallback: blocking start via QThread worker (used if SyncQueue not available)."""
        task_id = self.task.get("id")
        if task_id is None: return
        self._timer_btn.setEnabled(False)
        self._timer_btn.setText("Starting...")
        self._start_worker = StartTimeEntryWorker(self.time_entry_service, self.project_id, task_id, parent=self)
        self._start_worker.finished.connect(self._on_start_success)
        self._start_worker.error.connect(self._on_start_error)
        self._start_worker.finished.connect(self._start_worker.deleteLater)
        self._start_worker.error.connect(self._start_worker.deleteLater)
        self._start_worker_thread(self._start_worker)

    # ── Optimistic Stop (instant UI, background sync) ─────────────────────

    def _do_stop_optimistic(self) -> None:
        """Instantly update UI to stopped state, then queue API call."""
        # INSTANT: update UI to stopped state
        self._is_running = False
        frozen_elapsed = self._elapsed_seconds + self._local_tick
        self._elapsed_seconds = frozen_elapsed
        self._local_tick = 0
        self._time_label.setText(_fmt_seconds(self._elapsed_seconds))
        self._update_timer_button()
        self.timer_stopped.emit(self.task.get("id", -1))

    def _do_stop(self) -> None:
        """Fallback: blocking stop via QThread worker."""
        if self._entry_id is None: return
        self._timer_btn.setEnabled(False)
        self._timer_btn.setText("Stopping...")
        self._stop_worker = StopTimeEntryWorker(self.time_entry_service, self._entry_id, parent=self)
        self._stop_worker.finished.connect(self._on_stop_success)
        self._stop_worker.error.connect(self._on_stop_error)
        self._stop_worker.finished.connect(self._stop_worker.deleteLater)
        self._stop_worker.error.connect(self._stop_worker.deleteLater)

        self._start_worker_thread(self._stop_worker)

    # ── Sync callbacks (called by TaskSection when SyncQueue reports results) ──

    def on_sync_start_confirmed(self, entry_id: int) -> None:
        """Server confirmed timer start — update entry_id."""
        self._entry_id = entry_id

    def on_sync_start_failed(self, error_msg: str) -> None:
        """Server rejected timer start — revert UI to stopped state."""
        self._is_running = False
        self._entry_id = None
        self._local_tick = 0
        self._update_timer_button()
        self.timer_stopped.emit(self.task.get("id", -1))
        self.error_occurred.emit(f"Failed to start timer: {error_msg}")

    def on_sync_stop_confirmed(self, result: dict) -> None:
        """Server confirmed timer stop — reconcile final elapsed time."""
        server_seconds = result.get("total_seconds")
        if server_seconds is not None:
            self._elapsed_seconds += server_seconds
            self._time_label.setText(_fmt_seconds(self._elapsed_seconds))

    def on_sync_stop_failed(self, error_msg: str) -> None:
        """Server rejected timer stop — show warning but keep local state."""
        # Don't revert to running — the user intended to stop.
        # The SyncQueue will retry automatically.
        self.error_occurred.emit(f"Timer stop pending sync: {error_msg}")

    # ── Legacy worker callbacks (kept for fallback path) ──────────────────

    def _on_start_success(self, entry_id: int) -> None:
        self._entry_id = entry_id
        self._is_running = True
        self._local_tick = 0
        self._timer_btn.setEnabled(True)
        self._update_timer_button()
        self.timer_started.emit(self.task.get("id", -1), entry_id)

    def _on_start_error(self, msg: str) -> None:
        self._timer_btn.setEnabled(True)
        self._update_timer_button()
        if "already has an active timer" in msg.lower() or "409" in msg:
            self.active_timer_conflict.emit()
        else:
            self.error_occurred.emit(msg)

    def _on_stop_success(self, result: dict) -> None:
        self._is_running = False
        self._entry_id = None
        final_seconds = result.get("total_seconds", self._elapsed_seconds + self._local_tick)
        self._elapsed_seconds = final_seconds
        self._local_tick = 0
        self._time_label.setText(_fmt_seconds(self._elapsed_seconds))
        self._timer_btn.setEnabled(True)
        self._update_timer_button()
        self.timer_stopped.emit(self.task.get("id", -1))

    def _on_stop_error(self, msg: str) -> None:
        self._timer_btn.setEnabled(True)
        self._update_timer_button()
        self.error_occurred.emit(msg)

    def tick(self) -> None:
        if self._is_running:
            self._local_tick += 1
            total = self._elapsed_seconds + self._local_tick
            self._time_label.setText(_fmt_seconds(total))

    def set_running(self, running: bool, entry_id: Optional[int] = None, elapsed: int = 0) -> None:
        self._is_running = running
        self._entry_id = entry_id
        self._local_tick = elapsed
        self._timer_btn.setEnabled(True)
        self._update_timer_button()
        if not running:
            self._time_label.setText(_fmt_seconds(self._elapsed_seconds))
        else:
            self._time_label.setText(_fmt_seconds(self._elapsed_seconds + elapsed))

    def update_elapsed_seconds(self, session_elapsed: int) -> None:
        self._time_label.setText(_fmt_seconds(self._elapsed_seconds + session_elapsed))

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
        edit_action = menu.addAction("✎  Edit")
        dup_action = menu.addAction("⧉  Duplicate")
        menu.addSeparator()
        del_action = menu.addAction("🗑  Delete")
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
        time_entry_service: TimeEntryService,
        task_service: TaskService,
        tracking_manager = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.time_entry_service = time_entry_service
        self.task_service = task_service
        self._tracking_manager = tracking_manager
        self._tasks: List[Dict[str, Any]] = []
        self._project: Optional[Dict[str, Any]] = None
        self._project_color = "#3B82F6"
        self._task_rows: List[TaskRow] = []
        self._running_task_id: Optional[int] = None
        self._running_entry_id: Optional[int] = None
        self._user_id: Optional[int] = None
        self._running_elapsed_seconds = 0
        self._search_text = ""
        self.user_role = None
        self._sync_queue = None  # Set via set_sync_queue()
        self._local_cache = None  # Set via set_local_cache()
        self._has_loaded_tasks = False

        # Workers references — held to prevent QThread destroyed while running
        self._create_worker: Optional[CreateTaskWorker] = None
        self._update_worker: Optional[UpdateTaskWorker] = None
        self._delete_worker: Optional[DeleteTaskWorker] = None
        self._switch_stop_worker: Optional[StopTimeEntryWorker] = None
        self._switch_start_worker: Optional[StartTimeEntryWorker] = None
        self._running_workers = set()

        # Connect tracking manager signals or fall back to local timer
        if self._tracking_manager:
            self._tracking_manager.tracking_started.connect(self._on_tracking_started)
            self._tracking_manager.tracking_stopped.connect(self._on_tracking_stopped)
            self._tracking_manager.tick.connect(self._on_tracking_tick)
            self._tracking_manager.error_occurred.connect(self._on_tracking_error)
            self._tracking_manager.status_message.connect(self._on_tracking_status)
        else:
            # Local tick timer — fires every second when a task timer is running
            self._tick_timer = QTimer(self)
            self._tick_timer.timeout.connect(self._on_tick)
            self._tick_timer.start(1000)

        self._build_ui()

    def set_sync_queue(self, sync_queue) -> None:
        """Inject SyncQueue for background operations. Called by DashboardWindow."""
        self._sync_queue = sync_queue
        # Connect sync queue signals for result handling
        sync_queue.action_completed.connect(self._on_sync_action_completed)
        sync_queue.action_failed.connect(self._on_sync_action_failed)

    def set_local_cache(self, local_cache) -> None:
        """Inject LocalCache for timer state persistence."""
        self._local_cache = local_cache

    def set_user_role(self, role_name: str) -> None:
        self.user_role = role_name

    def set_user_id(self, user_id: int) -> None:
        self._user_id = user_id

    @property
    def is_admin(self) -> bool:
        return self.user_role in ["admin", "org_admin", "super_admin"]

    def _start_worker(self, worker) -> None:
        self._running_workers.add(worker)
        worker.finished.connect(lambda: self._running_workers.discard(worker))
        worker.error.connect(lambda: self._running_workers.discard(worker))
        worker.start()

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

        self._title_label = QLabel("My Tasks", header_row)
        self._title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.ExtraBold))
        self._title_label.setStyleSheet(f"color: {TEXT_PRIMARY};")
        title_hbox.addWidget(self._title_label)

        self._count_badge = QLabel("0", header_row)
        self._count_badge.setFixedSize(24, 24)
        self._count_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._count_badge.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._count_badge.setStyleSheet(f"background: #E2E8F0; color: {TEXT_SECONDARY}; border-radius: 12px; font-size: 10px;")
        title_hbox.addWidget(self._count_badge)

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
        self._search.setPlaceholderText("Search tasks...")
        self._search.setFixedSize(200, 32)
        self._search.textChanged.connect(self._on_search_changed)
        header_layout.addWidget(self._search)

        # Add Task button
        self._add_task_btn = QPushButton("+ Add Task", header_row)
        self._add_task_btn.setObjectName("AddTaskBtn")
        self._add_task_btn.setFixedSize(100, 32)
        self._add_task_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_task_btn.setEnabled(False)
        self._add_task_btn.clicked.connect(self._on_add_task_clicked)
        header_layout.addWidget(self._add_task_btn)

        # Refresh button
        self._refresh_btn = QPushButton("⟳ Refresh", header_row)
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
        self._count_badge.setText("…")
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

        if project:
            proj_name = project.get("project_name", "Project")
            self._title_label.setText(proj_name)
        else:
            self._title_label.setText("My Tasks")

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
                row._time_label.setText(_fmt_seconds(base_elapsed + row._local_tick))
            else:
                row._time_label.setText(_fmt_seconds(base_elapsed))

    def set_error(self, message: str) -> None:
        self._clear_rows()
        self._status_label.setText(f"⚠ {message}")
        self._status_label.show()
        self._has_loaded_tasks = False

    def clear(self) -> None:
        self._clear_rows()
        self._status_label.setText("Select a project to see tasks.")
        self._status_label.show()
        self._count_badge.setText("0")
        self._add_task_btn.setEnabled(False)
        self._tasks = []
        self._project = None
        self._update_current_task_indicator()
        self._has_loaded_tasks = False

    def apply_search(self, text: str) -> None:
        """Filters My Tasks search bar."""
        self._search.setText(text)

    def sync_active_timer(self, task_id: int, entry_id: int, elapsed: int = 0) -> None:
        """Called externally to set the currently running task & entry."""
        self._running_task_id = task_id
        self._running_entry_id = entry_id
        self._running_elapsed_seconds = elapsed
        for row in self._task_rows:
            if row.task.get("id") == task_id:
                row.set_running(True, entry_id, elapsed)
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
                # Fallback 1: tracking manager's active session task_name
                task_name = "Unknown"
                if self._tracking_manager:
                    session = self._tracking_manager.get_active_session()
                    if session and session.get("task_id") == self._running_task_id:
                        task_name = session.get("task_name") or "Unknown"
                # Fallback 2: task section's running task name (restored without tracking manager)
                if task_name == "Unknown" and getattr(self, "_running_task_name", None):
                    task_name = self._running_task_name

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
        project_name = self._project.get("project_name", "Project") if self._project else "Project"

        filtered = [
            t for t in self._tasks
            if self._search_text.lower() in (t.get("name") or t.get("task_name") or "").lower()
        ]

        self._count_badge.setText(str(len(filtered)))

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
                time_entry_service=self.time_entry_service,
                is_running=(task.get("id") == self._running_task_id),
                parent=self._rows_container,
            )
            if task.get("id") == self._running_task_id:
                row.set_running(True, self._running_entry_id, self._running_elapsed_seconds)

            row.start_requested.connect(self._handle_start_request)
            row.stop_requested.connect(self._handle_stop_request)
            row.edit_requested.connect(self._handle_edit_request)
            row.duplicate_requested.connect(self._handle_duplicate_request)
            row.delete_requested.connect(self._handle_delete_request)

            row.timer_started.connect(self._on_task_timer_started)
            row.timer_stopped.connect(self._on_task_timer_stopped)
            row.error_occurred.connect(self.error_occurred)
            row.active_timer_conflict.connect(self.active_timer_conflict.emit)

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

    # ── Task Switching workflow (Optimistic UI) ────────────────────────────────

    def _handle_start_request(self, row: TaskRow) -> None:
        if self._tracking_manager:
            row._timer_btn.setEnabled(False)
            row._timer_btn.setText("Starting...")
            task_name = row.task.get("name") or row.task.get("task_name") or "Unnamed Task"
            self._tracking_manager.start_tracking(row.project_id, row.task.get("id"), task_name)
        elif self._sync_queue:
            self._handle_start_optimistic(row)
        elif self._running_task_id is None:
            row._do_start()
        else:
            self._do_task_switch_legacy(self._running_task_id, row)

    def _handle_stop_request(self, row: TaskRow) -> None:
        if self._tracking_manager:
            row._timer_btn.setEnabled(False)
            row._timer_btn.setText("Stopping...")
            self._tracking_manager.stop_tracking()
        elif self._sync_queue:
            self._handle_stop_optimistic(row)
        else:
            row._do_stop()

    def _handle_start_optimistic(self, row: TaskRow) -> None:
        """Optimistic start: instant UI update, then queue background sync."""
        task_id = row.task.get("id")
        if task_id is None:
            return

        if self._running_task_id is not None and self._running_task_id != task_id:
            # Switch: stop old task optimistically + start new one
            self._do_task_switch_optimistic(self._running_task_id, row)
            return

        # Simple start — no timer currently running
        row._do_start_optimistic()
        self._running_task_id = task_id
        self._running_entry_id = None  # Pending server confirmation
        self._running_elapsed_seconds = 0
        self.timer_state_changed.emit(True)
        self._update_current_task_indicator()
        self._persist_timer_state()

        # Queue background API call
        action_id = self._sync_queue._cache.enqueue_action(
            "start_timer",
            {"project_id": row.project_id, "task_id": task_id},
            priority=2,
            idempotency_key=f"start_{task_id}",
        )
        row._pending_action_id = action_id
        self._sync_queue.wake()

    def _handle_stop_optimistic(self, row: TaskRow) -> None:
        """Optimistic stop: instant UI update, then queue background sync."""
        entry_id = row._entry_id
        task_id = row.task.get("id")
        elapsed = self._running_elapsed_seconds

        # Accumulate tracked duration into local SQLite cache before stopping
        if self._local_cache and elapsed > 0:
            from datetime import date
            today_str = date.today().isoformat()
            self._local_cache.add_elapsed_to_cached_time_entry(today_str, task_id, elapsed)

        # INSTANT: update UI
        row._do_stop_optimistic()
        self._running_task_id = None
        self._running_entry_id = None
        self._running_elapsed_seconds = 0
        self.timer_state_changed.emit(False)
        self._update_current_task_indicator()
        self._persist_timer_state()

        # Queue background API call only if we have a real entry_id
        if entry_id and entry_id > 0:
            action_id = self._sync_queue._cache.enqueue_action(
                "stop_timer",
                {"entry_id": entry_id, "task_id": task_id},
                priority=1,
                idempotency_key=f"stop_{entry_id}",
            )
            row._pending_action_id = action_id
            self._sync_queue.wake()

    def _do_task_switch_optimistic(self, old_task_id: int, new_row: TaskRow) -> None:
        """Optimistic switch: instantly update both rows, queue atomic switch."""
        old_row = next((r for r in self._task_rows if r.task.get("id") == old_task_id), None)
        old_entry_id = self._running_entry_id
        new_task_id = new_row.task.get("id")

        # INSTANT: stop old row visually
        if old_row:
            old_row._do_stop_optimistic()

        # Accumulate tracked duration for old task into local SQLite cache
        elapsed = self._running_elapsed_seconds
        if self._local_cache and elapsed > 0:
            from datetime import date
            today_str = date.today().isoformat()
            self._local_cache.add_elapsed_to_cached_time_entry(today_str, old_task_id, elapsed)

        # INSTANT: start new row visually
        new_row._do_start_optimistic()
        self._running_task_id = new_task_id
        self._running_entry_id = None  # Pending server confirmation
        self._running_elapsed_seconds = 0
        self.timer_state_changed.emit(True)
        self._update_current_task_indicator()
        self._persist_timer_state()

        # Queue background atomic switch
        if old_entry_id and old_entry_id > 0:
            action_id = self._sync_queue._cache.enqueue_action(
                "switch_timer",
                {
                    "old_entry_id": old_entry_id,
                    "old_task_id": old_task_id,
                    "new_project_id": new_row.project_id,
                    "new_task_id": new_task_id,
                },
                priority=3,
                idempotency_key=f"switch_{old_task_id}_{new_task_id}",
            )
            new_row._pending_action_id = action_id
        else:
            # Old timer didn't have a server entry_id yet, just start new
            action_id = self._sync_queue._cache.enqueue_action(
                "start_timer",
                {"project_id": new_row.project_id, "task_id": new_task_id},
                priority=2,
                idempotency_key=f"start_{new_task_id}",
            )
            new_row._pending_action_id = action_id
        self._sync_queue.wake()

    # ── Sync Queue Result Handlers ────────────────────────────────────────────

    def _on_sync_action_completed(self, action_id: str, action_type: str, result: dict) -> None:
        """Handle successful background sync operations."""
        if action_type == "start_timer":
            entry_id = result.get("entry_id")
            task_id = result.get("task_id")
            if entry_id and task_id:
                self._running_entry_id = entry_id
                # Update the row with the confirmed entry_id
                for row in self._task_rows:
                    if row.task.get("id") == task_id and row._pending_action_id == action_id:
                        row.on_sync_start_confirmed(entry_id)
                        row._pending_action_id = None
                        break
                self._persist_timer_state()

        elif action_type == "stop_timer":
            task_id = result.get("task_id") if isinstance(result, dict) else None
            for row in self._task_rows:
                if row._pending_action_id == action_id:
                    row.on_sync_stop_confirmed(result)
                    row._pending_action_id = None
                    break

        elif action_type == "switch_timer":
            new_entry_id = result.get("new_entry_id")
            new_task_id = result.get("new_task_id")
            old_task_id = result.get("old_task_id")
            stop_result = result.get("stop_result", {})

            if new_entry_id and new_task_id:
                self._running_entry_id = new_entry_id
                for row in self._task_rows:
                    if row.task.get("id") == new_task_id:
                        row.on_sync_start_confirmed(new_entry_id)
                        row._pending_action_id = None
                    elif row.task.get("id") == old_task_id:
                        row.on_sync_stop_confirmed(stop_result)
                        row._pending_action_id = None
                self._persist_timer_state()

        elif action_type in ("create_task", "update_task", "delete_task"):
            self.task_action_succeeded.emit(f"Task {action_type.replace('_', ' ')}d successfully.")

    def _on_sync_action_failed(self, action_id: str, action_type: str, error: str, will_retry: bool) -> None:
        """Handle failed background sync operations."""
        if action_type == "start_timer" and not will_retry:
            # Revert optimistic start
            for row in self._task_rows:
                if row._pending_action_id == action_id:
                    row.on_sync_start_failed(error)
                    row._pending_action_id = None
                    break
            if self._running_task_id is not None:
                self._running_task_id = None
                self._running_entry_id = None
                self.timer_state_changed.emit(False)
                self._update_current_task_indicator()

        elif action_type == "stop_timer" and not will_retry:
            for row in self._task_rows:
                if row._pending_action_id == action_id:
                    row.on_sync_stop_failed(error)
                    row._pending_action_id = None
                    break

        elif action_type == "switch_timer" and not will_retry:
            self.error_occurred.emit(f"Timer switch failed: {error}")

        elif action_type in ("create_task", "update_task", "delete_task") and not will_retry:
            self.error_occurred.emit(f"Task operation failed: {error}")

    # ── Timer state persistence ───────────────────────────────────────────────

    def _persist_timer_state(self) -> None:
        """Save current timer state to local cache for crash recovery."""
        if not self._local_cache:
            return
        try:
            state = {
                "running_task_id": self._running_task_id,
                "running_entry_id": self._running_entry_id,
                "running_elapsed_seconds": self._running_elapsed_seconds,
            }
            self._local_cache.save_app_state("timer_state", state)
        except Exception:
            pass

    # ── Legacy task switch (fallback when SyncQueue is not available) ──────────

    def _do_task_switch_legacy(self, old_task_id: int, new_row: TaskRow) -> None:
        # Find the old row
        old_row = next((r for r in self._task_rows if r.task.get("id") == old_task_id), None)

        # Disable all timer buttons and set loading text
        for r in self._task_rows:
            r._timer_btn.setEnabled(False)

        if old_row:
            old_row._timer_btn.setText("Switching...")
        new_row._timer_btn.setText("Switching...")

        # Setup Stop Worker for the old entry
        self._switch_stop_worker = StopTimeEntryWorker(self.time_entry_service, self._running_entry_id, parent=self)

        def on_stop_success(result):
            if old_row:
                old_row.set_running(False)
                final_seconds = result.get("total_seconds", old_row._elapsed_seconds + old_row._local_tick)
                old_row._elapsed_seconds = final_seconds
                old_row._local_tick = 0
                old_row._time_label.setText(_fmt_seconds(final_seconds))

            self._running_task_id = None
            self._running_entry_id = None
            self.timer_state_changed.emit(False)

            # Now start the new task
            self._do_switch_start(new_row)

        def on_stop_error(msg):
            # Re-enable rows
            for r in self._task_rows:
                r._timer_btn.setEnabled(True)
                r._update_timer_button()
            self.error_occurred.emit(f"Unable to switch timer. The current timer could not be stopped: {msg}")

        self._switch_stop_worker.finished.connect(on_stop_success)
        self._switch_stop_worker.error.connect(on_stop_error)
        self._switch_stop_worker.finished.connect(self._switch_stop_worker.deleteLater)
        self._switch_stop_worker.error.connect(self._switch_stop_worker.deleteLater)
        self._start_worker(self._switch_stop_worker)

    def _do_switch_start(self, new_row: TaskRow) -> None:
        task_id = new_row.task.get("id")
        self._switch_start_worker = StartTimeEntryWorker(self.time_entry_service, new_row.project_id, task_id, parent=self)


        def on_start_success(entry_id):
            for r in self._task_rows:
                r._timer_btn.setEnabled(True)

            new_row.set_running(True, entry_id)
            self._running_task_id = task_id
            self._running_entry_id = entry_id
            self._running_elapsed_seconds = 0
            self.timer_state_changed.emit(True)
            self._update_current_task_indicator()

        def on_start_error(msg):
            for r in self._task_rows:
                r._timer_btn.setEnabled(True)
                r._update_timer_button()
            self.active_timer_conflict.emit()
            self.error_occurred.emit(f"Failed to start new timer: {msg}")

        self._switch_start_worker.finished.connect(on_start_success)
        self._switch_start_worker.error.connect(on_start_error)
        self._switch_start_worker.finished.connect(self._switch_start_worker.deleteLater)
        self._switch_start_worker.error.connect(self._switch_start_worker.deleteLater)
        self._start_worker(self._switch_start_worker)

    def _on_tracking_started(self, session_data: dict) -> None:
        task_id = session_data["task_id"]
        entry_id = session_data["entry_id"]
        elapsed = session_data.get("elapsed", 0)
        
        # Stop previously running row visually if switching tasks
        if self._running_task_id is not None and self._running_task_id != task_id:
            for row in self._task_rows:
                if row.task.get("id") == self._running_task_id:
                    row.set_running(False)
                    break

        self._running_task_id = task_id
        self._running_entry_id = entry_id
        self._running_elapsed_seconds = elapsed

        # Enable all buttons, set active row running
        for row in self._task_rows:
            row._timer_btn.setEnabled(True)
            if row.task.get("id") == task_id:
                row.set_running(True, entry_id, elapsed)
            else:
                row.set_running(False)

        self.timer_state_changed.emit(True)
        self._update_current_task_indicator()

    def _on_tracking_stopped(self, result: dict) -> None:
        stopped_task_id = self._running_task_id
        
        # Enable all buttons, stop running row visually
        for row in self._task_rows:
            row._timer_btn.setEnabled(True)
            if row.task.get("id") == stopped_task_id:
                server_seconds = result.get("total_seconds")
                if server_seconds is not None:
                    row._elapsed_seconds = server_seconds
                row.set_running(False)

        self._running_task_id = None
        self._running_entry_id = None
        self._running_elapsed_seconds = 0

        self.timer_state_changed.emit(False)
        self._update_current_task_indicator()

    def _on_tracking_tick(self, elapsed: int) -> None:
        self._running_elapsed_seconds = elapsed
        for row in self._task_rows:
            if row.task.get("id") == self._running_task_id:
                row.update_elapsed_seconds(elapsed)
                break

    def _on_tracking_error(self, error_msg: str) -> None:
        # Re-enable all buttons on error
        for row in self._task_rows:
            row._timer_btn.setEnabled(True)
            row._update_timer_button()
        self.error_occurred.emit(error_msg)

    def _on_tracking_status(self, status: str) -> None:
        pass

    def _on_task_timer_started(self, task_id: int, entry_id: int) -> None:
        if self._running_task_id is not None and self._running_task_id != task_id:
            for row in self._task_rows:
                if row.task.get("id") == self._running_task_id:
                    row.set_running(False)
                    break
        self._running_task_id = task_id
        self._running_entry_id = entry_id
        self._running_elapsed_seconds = 0
        self.timer_state_changed.emit(True)
        self._update_current_task_indicator()

    def _on_task_timer_stopped(self, task_id: int) -> None:
        if self._running_task_id == task_id:
            elapsed = self._running_elapsed_seconds
            if self._local_cache and elapsed > 0:
                from datetime import date
                today_str = date.today().isoformat()
                self._local_cache.add_elapsed_to_cached_time_entry(today_str, task_id, elapsed)
            self._running_task_id = None
            self._running_entry_id = None
            self._running_elapsed_seconds = 0
        self.timer_state_changed.emit(False)
        self._update_current_task_indicator()

    def _on_tick(self) -> None:
        if self._running_task_id is not None:
            self._running_elapsed_seconds += 1
        for row in self._task_rows:
            row.tick()

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
            self._create_worker = CreateTaskWorker(
                self.task_service, self._project.get("id"),
                data["task_name"], assignee_id, parent=self
            )
            self._create_worker.finished.connect(lambda _: self.task_action_succeeded.emit("Task created successfully."))
            self._create_worker.error.connect(self.error_occurred.emit)
            self._create_worker.finished.connect(self._create_worker.deleteLater)
            self._create_worker.error.connect(self._create_worker.deleteLater)
            self._start_worker(self._create_worker)

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

            self._update_worker = UpdateTaskWorker(
                self.task_service, row.project_id, row.task.get("id"),
                data["task_name"], data["status_id"], parent=self
            )
            self._update_worker.finished.connect(lambda _: self.task_action_succeeded.emit("Task updated successfully."))
            self._update_worker.error.connect(self.error_occurred.emit)
            self._update_worker.finished.connect(self._update_worker.deleteLater)
            self._update_worker.error.connect(self._update_worker.deleteLater)
            self._start_worker(self._update_worker)

    def _handle_duplicate_request(self, row: TaskRow) -> None:
        orig_name = row.task.get("name") or row.task.get("task_name") or "Task"
        orig_desc = row.task.get("description") or ""
        new_desc = orig_desc
        if "[duplicate]" not in orig_desc:
            new_desc = f"{orig_desc}\n[duplicate]".strip()

        self._create_worker = CreateTaskWorker(
            self.task_service, row.project_id,
            f"{orig_name} (Copy)", row.task.get("assignee_id") or 1, parent=self
        )
        self._create_worker.finished.connect(lambda _: self.task_action_succeeded.emit("Task duplicated successfully."))
        self._create_worker.error.connect(self.error_occurred.emit)
        self._create_worker.finished.connect(self._create_worker.deleteLater)
        self._create_worker.error.connect(self._create_worker.deleteLater)
        self._start_worker(self._create_worker)

    def _handle_delete_request(self, row: TaskRow) -> None:
        task_name = row.task.get("name") or row.task.get("task_name") or "Task"
        dialog = DeleteConfirmDialog(task_name, is_admin=self.is_admin, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._delete_worker = DeleteTaskWorker(self.task_service, row.project_id, row.task.get("id"), parent=self)
            self._delete_worker.finished.connect(lambda _: self.task_action_succeeded.emit("Task deleted successfully."))
            self._delete_worker.error.connect(self.error_occurred.emit)
            self._delete_worker.finished.connect(self._delete_worker.deleteLater)
            self._delete_worker.error.connect(self._delete_worker.deleteLater)
            self._start_worker(self._delete_worker)

