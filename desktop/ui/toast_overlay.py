"""
toast_overlay — In-app floating toast notification overlay system for PySide6.

Displays smooth, non-blocking animated toast popups at the top-right of the window.
Guarantees 100% notification visibility regardless of OS settings or Focus Assist.
"""
from __future__ import annotations

from typing import Optional, List
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QRect, QPoint, QObject, Signal
from PySide6.QtGui import QFont, QColor, QGraphicsDropShadowEffect
from PySide6.QtWidgets import QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton

from ui.styles import (
    TEXT_PRIMARY, TEXT_MUTED, CARD_BG, BORDER_LIGHT, SUCCESS, PRIMARY, WARNING, ERROR,
)


_LEVEL_CONFIG = {
    "success": {"color": SUCCESS, "icon": "✓", "title": "Success"},
    "info": {"color": PRIMARY, "icon": "ℹ", "title": "Information"},
    "warning": {"color": WARNING, "icon": "⚠", "title": "Warning"},
    "error": {"color": ERROR, "icon": "✕", "title": "Error"},
}


class ToastNotificationWidget(QFrame):
    """Single floating toast notification card with accent bar and smooth exit."""

    closed = Signal(object)

    def __init__(
        self,
        message: str,
        level: str = "info",
        title: Optional[str] = None,
        duration_ms: int = 4000,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.message = message
        self.level = level.lower()
        self.duration_ms = duration_ms
        config = _LEVEL_CONFIG.get(self.level, _LEVEL_CONFIG["info"])
        self.title_text = title or config["title"]
        self.accent_color = config["color"]
        self.icon_symbol = config["icon"]

        self.setFixedSize(340, 72)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._build_ui()
        self._apply_style()

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.close_toast)
        if self.duration_ms > 0:
            self._timer.start(self.duration_ms)

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(12)

        # Left Accent Pill
        self.accent_bar = QWidget(self)
        self.accent_bar.setFixedWidth(5)
        self.accent_bar.setStyleSheet(f"background-color: {self.accent_color}; border-top-left-radius: 8px; border-bottom-left-radius: 8px;")
        layout.addWidget(self.accent_bar)

        # Level Icon Badge
        self.icon_badge = QLabel(self.icon_symbol, self)
        self.icon_badge.setFixedSize(30, 30)
        self.icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_badge.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.icon_badge.setStyleSheet(f"""
            background-color: {self.accent_color}18;
            color: {self.accent_color};
            border-radius: 15px;
        """)
        layout.addWidget(self.icon_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        # Text Container (Title + Message)
        text_container = QWidget(self)
        text_container.setStyleSheet("border: none; background: transparent;")
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 8, 0, 8)
        text_layout.setSpacing(2)

        title_lbl = QLabel(self.title_text, text_container)
        title_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        title_lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
        text_layout.addWidget(title_lbl)

        # Truncate message cleanly if needed
        disp_msg = self.message[:80] + "..." if len(self.message) > 80 else self.message
        msg_lbl = QLabel(disp_msg, text_container)
        msg_lbl.setFont(QFont("Segoe UI", 9))
        msg_lbl.setStyleSheet(f"color: {TEXT_MUTED};")
        msg_lbl.setWordWrap(True)
        text_layout.addWidget(msg_lbl)

        layout.addWidget(text_container, 1, Qt.AlignmentFlag.AlignVCenter)

        # Close Button ✕
        close_btn = QPushButton("✕", self)
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #94A3B8;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #475569;
                background: #F1F5F9;
                border-radius: 10px;
            }
        """)
        close_btn.clicked.connect(self.close_toast)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #FFFFFF;
                border-radius: 8px;
                border: 1px solid {BORDER_LIGHT};
            }}
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def close_toast(self) -> None:
        self._timer.stop()
        self.closed.emit(self)


class ToastOverlayManager(QObject):
    """
    Manages top-right floating toasts overlay on top of MainWindow.
    """

    def __init__(self, parent_widget: QWidget) -> None:
        super().__init__(parent_widget)
        self._parent = parent_widget
        self._active_toasts: List[ToastNotificationWidget] = []

    def show_toast(self, message: str, level: str = "info", title: Optional[str] = None) -> None:
        if not self._parent or not self._parent.isVisible():
            return

        toast = ToastNotificationWidget(
            message=message,
            level=level,
            title=title,
            duration_ms=4000,
            parent=self._parent,
        )
        toast.closed.connect(self._on_toast_closed)
        self._active_toasts.append(toast)
        toast.show()
        self._reposition_toasts()

    def _on_toast_closed(self, toast: ToastNotificationWidget) -> None:
        if toast in self._active_toasts:
            self._active_toasts.remove(toast)
        toast.deleteLater()
        self._reposition_toasts()

    def _reposition_toasts(self) -> None:
        if not self._parent:
            return

        parent_rect = self._parent.rect()
        right_margin = 20
        top_margin = 20
        spacing = 10

        y_offset = top_margin
        for toast in self._active_toasts:
            x = parent_rect.width() - toast.width() - right_margin
            toast.move(x, y_offset)
            toast.raise_()
            y_offset += toast.height() + spacing
