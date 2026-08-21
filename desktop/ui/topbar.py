"""
Top bar — white sticky header with date navigation, network status, and sync indicator.
"""
from datetime import date, timedelta
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QWidget
)

from ui.styles import (
    TOPBAR_BG, TOPBAR_BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
    TEXT_MUTED, CONTENT_BG, SUCCESS
)


def _format_date_win(d: date) -> str:
    """Windows-compatible date formatting."""
    return d.strftime("%B %d, %Y (%a)").replace(" 0", " ")


class TopBar(QFrame):
    """
    White top bar with:
    - Center date navigation (‹ previous day, › next day)
    - Right network status + sync indicator
    Emits: date_changed(date)
    """
    date_changed = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(56)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._connected = True
        self._latency_ms: Optional[int] = None
        self._selected_date = date.today()
        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # Spacer to center the date row
        layout.addStretch()

        # ── Date display ───────────────────────────────────────────
        self.date_row = QWidget(self)
        self.date_row.setObjectName("DateRow")
        
        date_layout = QHBoxLayout(self.date_row)
        date_layout.setContentsMargins(6, 4, 6, 4)
        date_layout.setSpacing(12)

        # Left chevron
        self.prev_btn = QPushButton("‹", self.date_row)
        self.prev_btn.setObjectName("DateNavBtn")
        self.prev_btn.setFixedSize(30, 30)
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setToolTip("Previous Day")
        self.prev_btn.clicked.connect(self._on_prev_day)
        date_layout.addWidget(self.prev_btn)

        # Date Label
        date_str = _format_date_win(self._selected_date)
        self._date_label = QLabel(date_str, self.date_row)
        self._date_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._date_label.setStyleSheet(f"color: {TEXT_PRIMARY}; padding: 0 4px;")
        date_layout.addWidget(self._date_label)

        # Right chevron
        self.next_btn = QPushButton("›", self.date_row)
        self.next_btn.setObjectName("DateNavBtn")
        self.next_btn.setFixedSize(30, 30)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setToolTip("Next Day")
        self.next_btn.clicked.connect(self._on_next_day)
        date_layout.addWidget(self.next_btn)
        
        layout.addWidget(self.date_row)

        layout.addStretch()

        # ── Status indicators (network + sync) ────────────────────
        self._status_frame = QFrame(self)
        self._status_frame.setObjectName("StatusFrame")
        status_layout = QHBoxLayout(self._status_frame)
        status_layout.setContentsMargins(12, 4, 12, 4)
        status_layout.setSpacing(10)

        # Sync indicator (shows pending action count)
        self._sync_label = QLabel("", self._status_frame)
        self._sync_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._sync_label.setStyleSheet("color: #F59E0B; background: transparent; border: none;")
        self._sync_label.hide()
        status_layout.addWidget(self._sync_label)

        # Network status dot + text
        self._status_dot = QLabel("●", self._status_frame)
        self._status_dot.setFont(QFont("Segoe UI", 9))
        self._status_dot.setStyleSheet(f"color: {SUCCESS}; background: transparent; border: none;")
        status_layout.addWidget(self._status_dot)

        self._status_text = QLabel("Online", self._status_frame)
        self._status_text.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        self._status_text.setStyleSheet(f"color: {TEXT_MUTED}; background: transparent; border: none;")
        status_layout.addWidget(self._status_text)

        layout.addWidget(self._status_frame)

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QFrame#TopBar {{
                background-color: {TOPBAR_BG};
                border-bottom: 1px solid {TOPBAR_BORDER};
            }}
            QWidget#DateRow {{
                background-color: {TOPBAR_BG};
                border: none;
                border-radius: 8px;
            }}
            QPushButton#DateNavBtn {{
                background: transparent;
                border: 1px solid {TOPBAR_BORDER};
                border-radius: 6px;
                color: {TEXT_PRIMARY};
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton#DateNavBtn:hover {{
                background-color: {CONTENT_BG};
                border-color: {TEXT_MUTED};
            }}
            QPushButton#DateNavBtn:pressed {{
                background-color: #E2E8F0;
            }}
            QFrame#StatusFrame {{
                background: transparent;
                border: none;
            }}
        """)

    def _on_prev_day(self) -> None:
        self._selected_date -= timedelta(days=1)
        self._update_date_display()

    def _on_next_day(self) -> None:
        self._selected_date += timedelta(days=1)
        self._update_date_display()

    def _update_date_display(self) -> None:
        date_str = _format_date_win(self._selected_date)
        self._date_label.setText(date_str)
        self.date_changed.emit(self._selected_date)

    def _update_status_display(self) -> None:
        """Unified method to display network state and latency info."""
        if not self._connected:
            self._status_dot.setStyleSheet("color: #EF4444; background: transparent; border: none;")
            self._status_text.setText("Offline")
            self._status_text.setStyleSheet("color: #EF4444; background: transparent; border: none;")
        else:
            self._status_dot.setStyleSheet(f"color: {SUCCESS}; background: transparent; border: none;")
            if self._latency_ms is not None and self._latency_ms >= 1000:
                seconds = self._latency_ms / 1000.0
                self._status_text.setText(f"Online (Slow: {seconds:.1f}s)")
                self._status_text.setStyleSheet("color: #F59E0B; background: transparent; border: none;")
            else:
                self._status_text.setText("Online")
                self._status_text.setStyleSheet(f"color: {TEXT_MUTED}; background: transparent; border: none;")

    def set_connected(self, connected: bool) -> None:
        """Update the connection status indicator."""
        self._connected = connected
        self._update_status_display()

    def set_sync_status(self, pending_count: int) -> None:
        """Update the sync queue indicator."""
        if pending_count > 0:
            self._sync_label.setText(f"⟳ Syncing {pending_count}")
            self._sync_label.show()
        else:
            self._sync_label.hide()

    def set_latency(self, ms: int) -> None:
        """Optionally show latency info in the status area."""
        self._latency_ms = ms
        self._update_status_display()
