"""
Screenshot section — displays real screenshots from backend if any exist,
or shows an honest professional empty state.
Backend: GET /time-entry-screenshots returns TimeEntryScreenshotRead objects.
"""
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QPainter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QGridLayout, QPushButton, QSizePolicy
)

from ui.workers import LoadScreenshotsWorker
from app.api.client import ApiClient
from ui.styles import (
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BORDER_LIGHT, CARD_BG, CONTENT_BG
)


class ScreenshotCard(QFrame):
    """Single screenshot card showing metadata from the backend."""

    def __init__(self, screenshot: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.screenshot = screenshot
        self.setFixedHeight(110)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background: #1E293B;
                border-radius: 10px;
                border: 1px solid {BORDER_LIGHT};
            }}
        """)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        entry_id = self.screenshot.get("time_entry_id", "")
        created_at = self.screenshot.get("created_at", "")
        label = self.screenshot.get("label") or f"Entry #{entry_id}"
        image_url = self.screenshot.get("image_url") or ""

        # Top: label
        name_label = QLabel(label, self)
        name_label.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        name_label.setStyleSheet("color: white;")
        name_label.setWordWrap(False)
        layout.addWidget(name_label)

        # Middle: image URL hint
        if image_url:
            url_label = QLabel(image_url[:40] + "…" if len(image_url) > 40 else image_url, self)
        else:
            url_label = QLabel("No image URL", self)
        url_label.setFont(QFont("Segoe UI", 9))
        url_label.setStyleSheet(f"color: rgba(255,255,255,0.5);")
        layout.addWidget(url_label)

        layout.addStretch()

        # Bottom: timestamp
        if created_at:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                ts = dt.strftime("%I:%M %p")
            except Exception:
                ts = str(created_at)[:16]
        else:
            ts = "Unknown time"

        ts_label = QLabel(ts, self)
        ts_label.setFont(QFont("Courier New", 9))
        ts_label.setStyleSheet("color: rgba(255,255,255,0.4);")
        layout.addWidget(ts_label)


class ScreenshotSection(QWidget):
    """
    Recent Screenshots section.
    - Attempts to load real screenshots from GET /time-entry-screenshots
    - If none exist, shows an honest professional empty state
    - If backend capture is not running, communicates that clearly
    """

    def __init__(self, api_client: ApiClient, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.api_client = api_client
        self._screenshots: List[Dict[str, Any]] = []
        self._worker: Optional[LoadScreenshotsWorker] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Card
        card = QFrame(self)
        card.setObjectName("ScreenshotCard")
        card.setStyleSheet(f"""
            QFrame#ScreenshotCard {{
                background: {CARD_BG};
                border-radius: 12px;
                border: 1px solid {BORDER_LIGHT};
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # Header
        header = QWidget(card)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 14, 16, 14)

        self._title = QLabel("Recent Screenshots", header)
        self._title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self._title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        header_layout.addWidget(self._title)

        self._badge = QLabel("", header)
        self._badge.setFixedSize(24, 24)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._badge.setStyleSheet(f"background: #E2E8F0; color: {TEXT_SECONDARY}; border-radius: 12px;")
        self._badge.hide()
        header_layout.addWidget(self._badge)
        header_layout.addStretch()

        card_layout.addWidget(header)

        div = QFrame(card)
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"background: {BORDER_LIGHT}; border: none;")
        div.setFixedHeight(1)
        card_layout.addWidget(div)

        # Content area
        self._content_area = QWidget(card)
        self._content_layout = QVBoxLayout(self._content_area)
        self._content_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.addWidget(self._content_area)

        layout.addWidget(card)

        # Show loading initially
        self._show_loading()

    def _show_loading(self) -> None:
        self._clear_content()
        lbl = QLabel("Loading screenshots...", self._content_area)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px; padding: 30px;")
        self._content_layout.addWidget(lbl)

    def _show_empty_state(self) -> None:
        """Professional empty state — honest about screenshot capture not being enabled."""
        self._clear_content()
        self._badge.hide()

        container = QWidget(self._content_area)
        c_layout = QVBoxLayout(container)
        c_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.setSpacing(8)

        icon = QLabel("📷", container)
        icon.setFont(QFont("Segoe UI", 32))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(icon)

        title = QLabel("Screenshot capture is not enabled", container)
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(title)

        sub = QLabel(
            "Screenshots are captured automatically during active time tracking.\n"
            "Configure desktop screenshot tracking to see captured activity here.",
            container
        )
        sub.setFont(QFont("Segoe UI", 12))
        sub.setStyleSheet(f"color: {TEXT_MUTED};")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        c_layout.addWidget(sub)

        self._content_layout.addWidget(container)

    def _show_screenshots(self, screenshots: List[Dict[str, Any]]) -> None:
        self._clear_content()
        self._badge.setText(str(len(screenshots)))
        self._badge.show()

        grid_widget = QWidget(self._content_area)
        grid = QGridLayout(grid_widget)
        grid.setSpacing(12)
        grid.setContentsMargins(0, 0, 0, 0)

        cols = 4
        for i, shot in enumerate(screenshots):
            card = ScreenshotCard(shot, grid_widget)
            grid.addWidget(card, i // cols, i % cols)

        self._content_layout.addWidget(grid_widget)

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _load_screenshots(self) -> None:
        # Prevent double-load QThread destruction crash
        if self._worker is not None:
            try:
                if self._worker.isRunning():
                    self._worker.terminate()
                    self._worker.wait()
            except Exception:
                pass
            finally:
                self._worker = None

        self._worker = LoadScreenshotsWorker(self.api_client)
        self._worker.finished.connect(self._on_screenshots_loaded)
        self._worker.error.connect(self._on_load_error)
        self._worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.error.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_screenshots_loaded(self, screenshots: List[Dict[str, Any]]) -> None:
        self._screenshots = screenshots
        if screenshots:
            self._show_screenshots(screenshots)
        else:
            self._show_empty_state()

    def _on_load_error(self, error: str) -> None:
        self._show_empty_state()

    def refresh(self) -> None:
        """Re-fetch screenshots (e.g. after a timer stop)."""
        self._show_loading()
        self._load_screenshots()
