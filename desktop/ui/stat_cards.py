"""
stat_cards — the four summary cards between the header and the task list.

Presentation only. Every number shown here is handed in by DashboardWindow
from data it has already loaded (the day's time entries, the selected
project's tasks, TimerService's session); this module fetches nothing, owns
no timer and computes no elapsed time of its own.

Where a value is genuinely unknown -- no timer running, no entries for the
day -- the card says so rather than showing a zero that looks measured.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QVBoxLayout, QWidget
)

from core.time_format import format_hms
from ui import icons
from ui.styles import (
    BORDER_LIGHT, CARD_BG, CARD_RADIUS, STAT_TILE_GRADIENTS, SUCCESS,
    TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
)

#: The one authoritative duration formatter (core.time_format.format_hms).
_fmt = format_hms


class StatCard(QFrame):
    """One summary card: gradient icon tile, caption, value, sub-line.

    The optional progress bar is only shown for cards that have a real
    ratio to show (tasks completed); it stays hidden otherwise instead of
    rendering an empty track.
    """

    def __init__(
        self,
        caption: str,
        icon_name: str,
        tile: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("StatCard")
        self._tile_key = tile
        self._accent = STAT_TILE_GRADIENTS[tile][2]
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(96)
        self._build_ui(caption, icon_name)
        self._apply_style()

    def _build_ui(self, caption: str, icon_name: str) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 18, 14)
        layout.setSpacing(14)

        start, end, _accent = STAT_TILE_GRADIENTS[self._tile_key]
        self._tile = QLabel(self)
        self._tile.setFixedSize(48, 48)
        self._tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tile.setPixmap(icons.pixmap(icon_name, "#FFFFFF", 24))
        self._tile.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                        stop:0 {start}, stop:1 {end});
            border-radius: 14px;
            border: none;
        """)
        layout.addWidget(self._tile, 0, Qt.AlignmentFlag.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        self._caption = QLabel(caption.upper(), self)
        self._caption.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._caption.setStyleSheet(
            f"color: {TEXT_SECONDARY}; letter-spacing: 0.9px; background: transparent;"
        )
        text_col.addWidget(self._caption)

        self._value = QLabel("—", self)
        self._value.setFont(QFont("Segoe UI", 18, QFont.Weight.Black))
        self._value.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
        text_col.addWidget(self._value)

        self._progress = QProgressBar(self)
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 100)
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                background: #EEF1F7;
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: {self._accent};
                border-radius: 3px;
            }}
        """)
        self._progress.hide()
        text_col.addWidget(self._progress)

        self._sub = QLabel("", self)
        self._sub.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        self._sub.setStyleSheet(f"color: {TEXT_MUTED}; background: transparent;")
        text_col.addWidget(self._sub)

        layout.addLayout(text_col, 1)

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QFrame#StatCard {{
                background: {CARD_BG};
                border: 1px solid {BORDER_LIGHT};
                border-radius: {CARD_RADIUS}px;
            }}
        """)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_value(self, text: str, *, mono: bool = False) -> None:
        self._value.setFont(
            QFont("Consolas" if mono else "Segoe UI", 17 if mono else 18, QFont.Weight.Black)
        )
        self._value.setText(text)

    def set_sub(self, text: str, color: Optional[str] = None) -> None:
        self._sub.setText(text)
        self._sub.setStyleSheet(
            f"color: {color or TEXT_MUTED}; background: transparent;"
        )
        self._sub.setVisible(bool(text))

    def set_progress(self, percent: Optional[int]) -> None:
        """`None` hides the bar -- there is no ratio to show."""
        if percent is None:
            self._progress.hide()
            return
        self._progress.setValue(max(0, min(100, percent)))
        self._progress.show()


class StatCardsRow(QWidget):
    """The four cards, updated together from one snapshot.

    `update_stats` takes only values the dashboard already holds; nothing in
    this widget derives a duration or reads a service.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.total_card = StatCard("Total time today", "timer", "violet", self)
        self.tasks_card = StatCard("Tasks completed", "task_alt", "blue", self)
        self.active_card = StatCard("Active task", "trending_up", "green", self)
        self.workday_card = StatCard("Work day", "calendar_month", "amber", self)

        for card in (self.total_card, self.tasks_card, self.active_card, self.workday_card):
            layout.addWidget(card, 1)

        self.reset()

    def reset(self) -> None:
        """The signed-out / nothing-loaded state. Honest blanks, not zeros."""
        self.total_card.set_value("00:00:00", mono=True)
        self.total_card.set_sub("Not tracking")
        self.tasks_card.set_value("—")
        self.tasks_card.set_progress(None)
        self.tasks_card.set_sub("No project selected")
        self.active_card.set_value("No active task")
        self.active_card.set_sub("")
        self.workday_card.set_value("00:00:00", mono=True)
        self.workday_card.set_sub("No time logged")

    # ── Per-card updates ──────────────────────────────────────────────────────

    def set_total_seconds(self, seconds: int, tracking: bool) -> None:
        self.total_card.set_value(_fmt(max(0, seconds)), mono=True)
        self.total_card.set_sub(
            "Tracking now" if tracking else "Not tracking",
            SUCCESS if tracking else None,
        )

    def set_tasks_completed(self, completed: Optional[int], total: Optional[int]) -> None:
        if completed is None or total is None:
            self.tasks_card.set_value("—")
            self.tasks_card.set_progress(None)
            self.tasks_card.set_sub("No project selected")
            return
        self.tasks_card.set_value(f"{completed} / {total}")
        percent = round(completed / total * 100) if total else 0
        self.tasks_card.set_progress(percent if total else None)
        self.tasks_card.set_sub(f"{percent}% of this project's tasks" if total else "No tasks yet")

    def set_active_task(self, task_name: Optional[str], project_name: Optional[str]) -> None:
        if not task_name:
            self.active_card.set_value("No active task")
            self.active_card.set_sub("")
            return
        display = task_name if len(task_name) <= 24 else task_name[:23] + "…"
        self.active_card.set_value(display)
        self.active_card._value.setToolTip(task_name)
        self.active_card.set_sub(project_name or "In progress", SUCCESS)

    def set_work_day(self, span_seconds: Optional[int], first: Optional[str],
                     last: Optional[str]) -> None:
        """The span from the day's first tracked start to its last end.

        `None` means the day holds no entries at all -- said plainly rather
        than shown as a measured zero.
        """
        if span_seconds is None:
            self.workday_card.set_value("00:00:00", mono=True)
            self.workday_card.set_sub("No time logged")
            return
        self.workday_card.set_value(_fmt(max(0, span_seconds)), mono=True)
        self.workday_card.set_sub(
            f"{first} – {last}" if first and last else "First to last entry"
        )
