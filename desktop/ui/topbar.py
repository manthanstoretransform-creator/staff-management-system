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

from ui import icons
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
    - Center date navigation (chevron icons: previous day, next day)
    - Right network status + sync indicator
    Emits: date_changed(date)
    """
    date_changed = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(56)
        self.setFrameShape(QFrame.Shape.NoFrame)
        #: Starts UNKNOWN, not "connected". Showing "Online" before a single
        #: probe has run publishes a state nobody measured.
        self._state = "UNKNOWN"
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
        self.prev_btn = QPushButton(self.date_row)
        self.prev_btn.setIcon(icons.icon("chevron_left", TEXT_PRIMARY, 18))
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
        self.next_btn = QPushButton(self.date_row)
        self.next_btn.setIcon(icons.icon("chevron_right", TEXT_PRIMARY, 18))
        self.next_btn.setObjectName("DateNavBtn")
        self.next_btn.setFixedSize(30, 30)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setToolTip("Next Day")
        self.next_btn.clicked.connect(self._on_next_day)
        date_layout.addWidget(self.next_btn)
        
        layout.addWidget(self.date_row)
        self._update_next_button_state()

        layout.addStretch()

        # ── Status indicators (network + sync) ────────────────────
        self._status_frame = QFrame(self)
        self._status_frame.setObjectName("StatusFrame")
        status_layout = QHBoxLayout(self._status_frame)
        status_layout.setContentsMargins(12, 4, 12, 4)
        status_layout.setSpacing(10)

        # Sync indicator (shows pending action count)
        self._sync_widget = QWidget(self._status_frame)
        sync_layout = QHBoxLayout(self._sync_widget)
        sync_layout.setContentsMargins(0, 0, 0, 0)
        sync_layout.setSpacing(4)
        self._sync_icon = QLabel(self._sync_widget)
        self._sync_icon.setPixmap(icons.pixmap("refresh", "#F59E0B", 13))
        sync_layout.addWidget(self._sync_icon)
        self._sync_label = QLabel("", self._sync_widget)
        self._sync_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._sync_label.setStyleSheet("color: #F59E0B; background: transparent; border: none;")
        sync_layout.addWidget(self._sync_label)
        self._sync_widget.hide()
        status_layout.addWidget(self._sync_widget)

        # Network status dot + text
        self._status_dot = QLabel(self._status_frame)
        self._status_dot.setPixmap(icons.pixmap("circle_filled", SUCCESS, 9))
        status_layout.addWidget(self._status_dot)

        # Text is rendered from self._state below, never hardcoded: shipping a
        # literal "Online" here meant the very first frame asserted a
        # connectivity fact before any probe had run.
        self._status_text = QLabel(self._status_frame)
        self._status_text.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        status_layout.addWidget(self._status_text)
        self._update_status_display()

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
            QPushButton#DateNavBtn:disabled {{
                color: {TEXT_MUTED};
                border-color: {TOPBAR_BORDER};
                background: transparent;
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
        # Belt-and-suspenders: _update_next_button_state() already disables
        # the button at today, but a click event that was already queued
        # when the button became disabled must not be able to sneak past.
        if self._selected_date >= date.today():
            return
        self._selected_date += timedelta(days=1)
        self._update_date_display()

    def _update_date_display(self) -> None:
        date_str = _format_date_win(self._selected_date)
        self._date_label.setText(date_str)
        self._update_next_button_state()
        self.date_changed.emit(self._selected_date)

    def _update_next_button_state(self) -> None:
        """Future dates are never navigable -- there is nothing tracked
        there yet. Previous-date navigation is unaffected."""
        self.next_btn.setEnabled(self._selected_date < date.today())

    #: How each network state is presented. "Offline" is reserved for the one
    #: case where it is literally true — the machine cannot reach the network at
    #: all. A backend that is down is a different fact and says so, because
    #: telling a user with working Wi-Fi that they are offline is simply wrong.
    _STATE_DISPLAY = {
        "NO_NETWORK": ("Offline", "#EF4444"),
        "BACKEND_UNREACHABLE": ("Server unreachable", "#F59E0B"),
        "AUTH_REQUIRED": ("Sign-in required", "#F59E0B"),
        "UNKNOWN": ("Checking…", TEXT_MUTED),
        "NETWORK_AVAILABLE": ("Checking…", TEXT_MUTED),
    }

    def _update_status_display(self) -> None:
        """Render the status pill from the committed network state.

        The pill reflects NetworkService and nothing else. It used to be
        writable by any caller via set_connected(), and the dashboard called it
        from individual request handlers: one failed load flipped it to
        "Offline", NetworkService never changed state (it was still reachable),
        so its edge-triggered signal never fired and the pill stayed wrong
        indefinitely. That is why the app showed Offline with working Wi-Fi.
        """
        if self._state == "BACKEND_REACHABLE":
            self._status_dot.setPixmap(icons.pixmap("circle_filled", SUCCESS, 9))
            if self._latency_ms is not None and self._latency_ms >= 1000:
                seconds = self._latency_ms / 1000.0
                self._status_text.setText(f"Online (Slow: {seconds:.1f}s)")
                self._status_text.setStyleSheet(
                    "color: #F59E0B; background: transparent; border: none;")
            else:
                self._status_text.setText("Online")
                self._status_text.setStyleSheet(
                    f"color: {TEXT_MUTED}; background: transparent; border: none;")
            return

        label, color = self._STATE_DISPLAY.get(self._state, ("Offline", "#EF4444"))
        self._status_dot.setPixmap(icons.pixmap("circle_filled", color, 9))
        self._status_text.setText(label)
        self._status_text.setStyleSheet(
            f"color: {color}; background: transparent; border: none;")

    def set_network_state(self, state: str) -> None:
        """Set the displayed network state.

        Deliberately the ONLY way to change the pill, and it takes a
        NetworkState value rather than a bool so the display cannot lose the
        distinction between "no network" and "backend down". There is no
        set_connected(): a per-request success or failure is not a
        connectivity measurement and must not be able to write here.
        """
        self._state = state
        self._update_status_display()

    def set_sync_status(self, pending_count: int) -> None:
        """Update the sync queue indicator."""
        if pending_count > 0:
            self._sync_label.setText(f"Syncing {pending_count}")
            self._sync_widget.show()
        else:
            self._sync_widget.hide()

    def set_latency(self, ms: int) -> None:
        """Optionally show latency info in the status area."""
        self._latency_ms = ms
        self._update_status_display()
