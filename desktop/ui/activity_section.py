"""
Activity section — displays captured screenshots, active application usage,
and website URLs visited, using clean tabs and premium PySide6 UI styling.
"""
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QColor, QPainter, QLinearGradient, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QGridLayout, QPushButton, QSizePolicy, QStackedWidget,
    QProgressBar, QDialog
)

from app.api.client import ApiClient
from ui.styles import (
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BORDER_LIGHT, BORDER_MID, CARD_BG, CONTENT_BG, PRIMARY, SUCCESS, WARNING, ERROR
)

# ─── Mock Datasets ────────────────────────────────────────────────────────────

MOCK_SCREENSHOTS = [
    {
        "id": 1,
        "time_entry_id": 101,
        "created_at": "2026-08-21T10:30:00Z",
        "label": "Design System Redesign",
        "domain": "app.figma.com",
        "activity_percent": 85,
        "gradient_from": "#1E1B4B",
        "gradient_to": "#312E81",
        "favicon_letter": "F",
        "favicon_color": "#A855F7"
    },
    {
        "id": 2,
        "time_entry_id": 102,
        "created_at": "2026-08-21T10:20:00Z",
        "label": "Authentication Module Logic",
        "domain": "visualstudio.com",
        "activity_percent": 90,
        "gradient_from": "#0C1A2E",
        "gradient_to": "#0E3460",
        "favicon_letter": "V",
        "favicon_color": "#3B82F6"
    },
    {
        "id": 3,
        "time_entry_id": 103,
        "created_at": "2026-08-21T10:10:00Z",
        "label": "Dashboard Interface Layout",
        "domain": "app.analytics.com",
        "activity_percent": 75,
        "gradient_from": "#0F2027",
        "gradient_to": "#203A43",
        "favicon_letter": "A",
        "favicon_color": "#22C55E"
    },
    {
        "id": 4,
        "time_entry_id": 104,
        "created_at": "2026-08-21T10:00:00Z",
        "label": "Staff Directory Roadmap",
        "domain": "docs.google.com",
        "activity_percent": 80,
        "gradient_from": "#1A1A2E",
        "gradient_to": "#16213E",
        "favicon_letter": "G",
        "favicon_color": "#EAB308"
    },
    {
        "id": 5,
        "time_entry_id": 105,
        "created_at": "2026-08-21T09:50:00Z",
        "label": "Sprint Standup Planning",
        "domain": "slack.com",
        "activity_percent": 65,
        "gradient_from": "#1C1917",
        "gradient_to": "#292524",
        "favicon_letter": "S",
        "favicon_color": "#EC4899"
    },
    {
        "id": 6,
        "time_entry_id": 106,
        "created_at": "2026-08-21T09:40:00Z",
        "label": "Client Onboarding Feedback",
        "domain": "mail.google.com",
        "activity_percent": 70,
        "gradient_from": "#052E16",
        "gradient_to": "#14532D",
        "favicon_letter": "G",
        "favicon_color": "#F97316"
    }
]

MOCK_APPS = [
    {"name": "Visual Studio Code", "time_str": "2h 15m", "seconds": 8100, "percentage": 42, "color": "#3B82F6", "letter": "VS"},
    {"name": "Google Chrome", "time_str": "1h 42m", "seconds": 6120, "percentage": 31, "color": "#10B981", "letter": "GC"},
    {"name": "Slack", "time_str": "35m", "seconds": 2100, "percentage": 11, "color": "#EC4899", "letter": "S"},
    {"name": "Figma", "time_str": "18m", "seconds": 1080, "percentage": 6, "color": "#8B5CF6", "letter": "F"},
    {"name": "Postman", "time_str": "12m", "seconds": 720, "percentage": 4, "color": "#F97316", "letter": "P"},
    {"name": "Microsoft Teams", "time_str": "8m", "seconds": 480, "percentage": 2, "color": "#6366F1", "letter": "MS"},
    {"name": "Spotify", "time_str": "5m", "seconds": 300, "percentage": 1, "color": "#1DB954", "letter": "SP"},
    {"name": "Windows Terminal", "time_str": "3m", "seconds": 180, "percentage": 1, "color": "#4B5563", "letter": "WT"}
]

MOCK_URLS = [
    {"url": "github.com/staff-management-system/desktop/ui/activity_section.py", "title": "Staff Management System Repository", "time_str": "45m", "seconds": 2700, "color": "#0F172A", "letter": "GH"},
    {"url": "docs.python.org/3/library/pyside6.html", "title": "Python PySide6 Library Documentation", "time_str": "20m", "seconds": 1200, "color": "#3776AB", "letter": "PY"},
    {"url": "localhost:3000/showcase/dashboard", "title": "React Dashboard Interface Showcase", "time_str": "15m", "seconds": 900, "color": "#2563EB", "letter": "LH"},
    {"url": "chatgpt.com/c/chat-session-monitra-app-pyside6", "title": "AI Assistant Chat - UI Coding Help", "time_str": "10m", "seconds": 600, "color": "#10A37F", "letter": "AI"},
    {"url": "figma.com/file/monitra-design-tokens", "title": "Monitra Desktop App Design Mockups", "time_str": "8m", "seconds": 480, "color": "#F24E1E", "letter": "FG"},
    {"url": "stackoverflow.com/questions/tagged/pyside6", "title": "Stack Overflow Questions - PySide6 Layouts", "time_str": "6m", "seconds": 360, "color": "#F48024", "letter": "SO"},
    {"url": "google.com/search?q=pyside6+tabs+styling", "title": "Google Search - PySide6 tabs styling", "time_str": "4m", "seconds": 240, "color": "#4285F4", "letter": "G"}
]

# ─── Custom Widgets ───────────────────────────────────────────────────────────

class SimulatedScreenshotWidget(QWidget):
    """Draws a beautiful mock workspace layout with gradients simulating screenshots."""
    def __init__(self, from_hex: str, to_hex: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.from_color = QColor(from_hex)
        self.to_color = QColor(to_hex)
        self.setFixedHeight(120)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background gradient
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, self.from_color)
        gradient.setColorAt(1, self.to_color)
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Round corners
        r = 8
        painter.drawRoundedRect(self.rect(), r, r)

        # Simulating window chrome & content (code/dashboard layouts)
        # Top header
        painter.setBrush(QColor(255, 255, 255, 25))
        painter.drawRoundedRect(8, 8, self.width() - 16, 12, 3, 3)

        # Sidebar
        painter.setBrush(QColor(255, 255, 255, 15))
        painter.drawRoundedRect(8, 26, 24, self.height() - 34, 3, 3)

        # Content blocks
        painter.setBrush(QColor(255, 255, 255, 20))
        painter.drawRoundedRect(38, 26, 80, 10, 2, 2)
        painter.drawRoundedRect(38, 40, 50, 8, 2, 2)
        
        # Cards
        painter.setBrush(QColor(255, 255, 255, 10))
        card_w = (self.width() - 46 - 8) // 2
        painter.drawRoundedRect(38, 54, card_w, 35, 4, 4)
        painter.drawRoundedRect(38 + card_w + 6, 54, card_w, 35, 4, 4)


class ScreenshotPreviewDialog(QDialog):
    """Fullscreen-like lightbox dialog displaying the large mock screenshot."""
    def __init__(self, screenshot: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.resize(700, 480)
        self.setStyleSheet("""
            QDialog {
                background-color: #0F172A;
                border-radius: 16px;
                border: 1px solid rgba(255,255,255,0.15);
            }
        """)
        self._screenshot = screenshot
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget(self)
        header.setFixedHeight(60)
        header.setStyleSheet("""
            QWidget {
                background: #1E293B;
                border-top-left-radius: 15px;
                border-top-right-radius: 15px;
                border-bottom: 1px solid rgba(255,255,255,0.1);
            }
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 10, 20, 10)

        # Title / Domain Info
        title_container = QWidget(header)
        tc_layout = QVBoxLayout(title_container)
        tc_layout.setContentsMargins(0, 0, 0, 0)
        tc_layout.setSpacing(2)

        title_lbl = QLabel(self._screenshot.get("label", "Screenshot"), title_container)
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: white; border: none; background: transparent;")

        sub_lbl = QLabel(f"{self._screenshot.get('domain', '')} • {self._screenshot.get('created_at', '')[:16].replace('T', ' ')}", title_container)
        sub_lbl.setFont(QFont("Segoe UI", 9))
        sub_lbl.setStyleSheet("color: #94A3B8; border: none; background: transparent;")

        tc_layout.addWidget(title_lbl)
        tc_layout.addWidget(sub_lbl)
        h_layout.addWidget(title_container)

        h_layout.addStretch()

        # Activity badge
        act_percent = self._screenshot.get("activity_percent", 0)
        if act_percent >= 80:
            act_color = SUCCESS
        elif act_percent >= 50:
            act_color = WARNING
        else:
            act_color = ERROR

        act_lbl = QLabel(f"{act_percent}% Activity", header)
        act_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        act_lbl.setStyleSheet(f"""
            QLabel {{
                background: {act_color};
                color: white;
                border-radius: 6px;
                padding: 4px 8px;
                border: none;
            }}
        """)
        h_layout.addWidget(act_lbl)

        # Close button
        close_btn = QPushButton("✕", header)
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.08);
                color: #94A3B8;
                border-radius: 6px;
                font-size: 12px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.15);
                color: white;
            }
        """)
        close_btn.clicked.connect(self.close)
        h_layout.addWidget(close_btn)

        layout.addWidget(header)

        # Large Image view (Simulated screenshot at scale)
        self.large_preview = SimulatedScreenshotWidget(
            self._screenshot.get("gradient_from", "#1E1B4B"),
            self._screenshot.get("gradient_to", "#312E81"),
            self
        )
        self.large_preview.setFixedHeight(360)
        layout.addWidget(self.large_preview)

        # Footer
        footer = QWidget(self)
        footer.setFixedHeight(50)
        footer.setStyleSheet("""
            QWidget {
                background: #0F172A;
                border-bottom-left-radius: 15px;
                border-bottom-right-radius: 15px;
                border-top: 1px solid rgba(255,255,255,0.05);
            }
        """)
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(20, 10, 20, 10)

        # Favicon badge + label
        fav_badge = QLabel(self._screenshot.get("favicon_letter", "W")[:1], footer)
        fav_badge.setFixedSize(22, 22)
        fav_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fav_badge.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        fav_badge.setStyleSheet(f"""
            background-color: {self._screenshot.get('favicon_color', '#2563EB')};
            color: white;
            border-radius: 11px;
            border: none;
        """)
        f_layout.addWidget(fav_badge)

        domain_lbl = QLabel(self._screenshot.get("domain", ""), footer)
        domain_lbl.setFont(QFont("Segoe UI", 10))
        domain_lbl.setStyleSheet("color: #94A3B8; border: none; background: transparent;")
        f_layout.addWidget(domain_lbl)

        f_layout.addStretch()

        time_lbl = QLabel(self._screenshot.get("created_at", "")[:16], footer)
        time_lbl.setFont(QFont("Segoe UI", 9))
        time_lbl.setStyleSheet("color: #64748B; border: none; background: transparent;")
        f_layout.addWidget(time_lbl)

        layout.addWidget(footer)


class ScreenshotCard(QFrame):
    """Card widget representing a single screenshot with simulated preview thumbnail and detailed information footer."""
    clicked = Signal(dict)

    def __init__(self, screenshot: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.screenshot = screenshot
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background: #FFFFFF;
                border-radius: 12px;
                border: 1px solid {BORDER_LIGHT};
            }}
            QFrame:hover {{
                border-color: {BORDER_MID};
            }}
        """)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Image thumbnail area
        self.thumbnail = SimulatedScreenshotWidget(
            self.screenshot.get("gradient_from", "#1E1B4B"),
            self.screenshot.get("gradient_to", "#312E81"),
            self
        )
        self.thumbnail.setCursor(Qt.CursorShape.PointingHandCursor)
        self.thumbnail.mousePressEvent = self._on_thumbnail_clicked
        layout.addWidget(self.thumbnail)

        # Info row: Favicon circle + label & domain
        info_row = QWidget(self)
        info_row.setStyleSheet("border: none; background: transparent;")
        info_layout = QHBoxLayout(info_row)
        info_layout.setContentsMargins(6, 4, 6, 6)
        info_layout.setSpacing(8)

        fav_badge = QLabel(self.screenshot.get("favicon_letter", "W")[:1], info_row)
        fav_badge.setFixedSize(20, 20)
        fav_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fav_badge.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        fav_badge.setStyleSheet(f"""
            background-color: {self.screenshot.get('favicon_color', '#2563EB')};
            color: white;
            border-radius: 10px;
            border: none;
        """)
        info_layout.addWidget(fav_badge)

        text_container = QWidget(info_row)
        tc_layout = QVBoxLayout(text_container)
        tc_layout.setContentsMargins(0, 0, 0, 0)
        tc_layout.setSpacing(1)

        domain_lbl = QLabel(self.screenshot.get("domain", ""), text_container)
        domain_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        domain_lbl.setStyleSheet(f"color: {PRIMARY};")
        domain_lbl.setWordWrap(False)

        label_lbl = QLabel(self.screenshot.get("label", ""), text_container)
        label_lbl.setFont(QFont("Segoe UI", 9))
        label_lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
        label_lbl.setWordWrap(False)

        tc_layout.addWidget(domain_lbl)
        tc_layout.addWidget(label_lbl)
        info_layout.addWidget(text_container, 1)

        layout.addWidget(info_row)

        # Overlay timestamps inside the card thumbnail
        thumb_layout = QVBoxLayout(self.thumbnail)
        thumb_layout.setContentsMargins(8, 8, 8, 8)
        
        top_spacer = QWidget(self.thumbnail)
        top_spacer.setStyleSheet("background: transparent; border: none;")
        thumb_layout.addWidget(top_spacer, 1)

        meta_row = QWidget(self.thumbnail)
        meta_row.setStyleSheet("background: transparent; border: none;")
        meta_layout = QHBoxLayout(meta_row)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(0)

        created_at = self.screenshot.get("created_at", "")
        if created_at:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                ts = dt.strftime("%I:%M %p")
            except Exception:
                ts = str(created_at)[:16]
        else:
            ts = "10:30 AM"

        ts_lbl = QLabel(ts, meta_row)
        ts_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        ts_lbl.setStyleSheet("""
            background-color: rgba(0, 0, 0, 0.6);
            color: white;
            border-radius: 4px;
            padding: 2px 6px;
            border: none;
        """)
        meta_layout.addWidget(ts_lbl)

        meta_layout.addStretch()

        act_percent = self.screenshot.get("activity_percent", 0)
        if act_percent >= 80:
            act_color = SUCCESS
        elif act_percent >= 50:
            act_color = WARNING
        else:
            act_color = ERROR

        act_lbl = QLabel(f"{act_percent}% Activity", meta_row)
        act_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        act_lbl.setStyleSheet(f"""
            background-color: {act_color};
            color: white;
            border-radius: 4px;
            padding: 2px 6px;
            border: none;
        """)
        meta_layout.addWidget(act_lbl)
        thumb_layout.addWidget(meta_row)

    def _on_thumbnail_clicked(self, event) -> None:
        self.clicked.emit(self.screenshot)


class AppRowWidget(QFrame):
    """Displays a single tracked application with active time and usage progress bar."""
    def __init__(self, app_data: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.app_data = app_data
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #FFFFFF;
                border-radius: 10px;
                border: 1px solid {BORDER_LIGHT};
            }}
            QFrame:hover {{
                border-color: {BORDER_MID};
                background-color: #F8FAFC;
            }}
        """)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        # App Icon Circle Badge
        self.icon_badge = QLabel(self.app_data.get("letter", "A")[:2], self)
        self.icon_badge.setFixedSize(36, 36)
        self.icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_badge.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.icon_badge.setStyleSheet(f"""
            background-color: {self.app_data.get('color', '#3B82F6')}20;
            color: {self.app_data.get('color', '#3B82F6')};
            border-radius: 18px;
            border: 1.5px solid {self.app_data.get('color', '#3B82F6')};
        """)
        layout.addWidget(self.icon_badge)

        # Name and bar container
        mid_container = QWidget(self)
        mid_container.setStyleSheet("border: none; background: transparent;")
        mid_layout = QVBoxLayout(mid_container)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(6)

        name_lbl = QLabel(self.app_data.get("name", "Application"), mid_container)
        name_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        name_lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
        mid_layout.addWidget(name_lbl)

        # Usage progress bar
        self.prog_bar = QProgressBar(mid_container)
        self.prog_bar.setFixedHeight(6)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(self.app_data.get("percentage", 0))
        self.prog_bar.setStyleSheet(f"""
            QProgressBar {{
                background: #F1F5F9;
                border-radius: 3px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {self.app_data.get('color', PRIMARY)};
                border-radius: 3px;
            }}
        """)
        mid_layout.addWidget(self.prog_bar)
        layout.addWidget(mid_container, 1)

        # Duration & relative percentages
        meta_container = QWidget(self)
        meta_container.setStyleSheet("border: none; background: transparent;")
        meta_layout = QVBoxLayout(meta_container)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(2)
        meta_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        time_lbl = QLabel(self.app_data.get("time_str", "0m"), meta_container)
        time_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        time_lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        pct_lbl = QLabel(f"{self.app_data.get('percentage', 0)}% of total active time", meta_container)
        pct_lbl.setFont(QFont("Segoe UI", 9))
        pct_lbl.setStyleSheet(f"color: {TEXT_MUTED};")
        pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        meta_layout.addWidget(time_lbl)
        meta_layout.addWidget(pct_lbl)
        layout.addWidget(meta_container)


class URLRowWidget(QFrame):
    """Displays a single tracked website URL, page title, and time spent, with text truncation and tooltip."""
    def __init__(self, url_data: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.url_data = url_data
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #FFFFFF;
                border-radius: 10px;
                border: 1px solid {BORDER_LIGHT};
            }}
            QFrame:hover {{
                border-color: {BORDER_MID};
                background-color: #F8FAFC;
            }}
        """)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        # Website Favicon Badge
        self.icon_badge = QLabel(self.url_data.get("letter", "W")[:2], self)
        self.icon_badge.setFixedSize(36, 36)
        self.icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_badge.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.icon_badge.setStyleSheet(f"""
            background-color: {self.url_data.get('color', '#3B82F6')}15;
            color: {self.url_data.get('color', '#3B82F6')};
            border-radius: 18px;
            border: 1.5px solid {self.url_data.get('color', '#3B82F6')};
        """)
        layout.addWidget(self.icon_badge)

        # Title & URL container
        mid_container = QWidget(self)
        mid_container.setStyleSheet("border: none; background: transparent;")
        mid_layout = QVBoxLayout(mid_container)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(2)

        title_lbl = QLabel(self.url_data.get("title", "Website page"), mid_container)
        title_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        title_lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
        mid_layout.addWidget(title_lbl)

        # Auto-truncated URL with hover tooltip
        url_text = self.url_data.get("url", "")
        truncated_url = url_text[:80] + "..." if len(url_text) > 80 else url_text
        url_lbl = QLabel(truncated_url, mid_container)
        url_lbl.setFont(QFont("Segoe UI", 9))
        url_lbl.setStyleSheet(f"color: {PRIMARY};")
        url_lbl.setToolTip(url_text)  # Shows full URL natively on hover
        mid_layout.addWidget(url_lbl)
        
        layout.addWidget(mid_container, 1)

        # Duration
        time_lbl = QLabel(self.url_data.get("time_str", "0m"), self)
        time_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        time_lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(time_lbl)

# ─── Tab Sub-Views ────────────────────────────────────────────────────────────

class ScreenshotsTabView(QWidget):
    """Grid display of captures with full preview lightbox and empty/loading state support."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._screenshots = []
        self._mode = "data"
        self._build_ui()

    def _build_ui(self) -> None:
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.render_view()

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.render_view()

    def set_data(self, data: List[Dict[str, Any]]) -> None:
        self._screenshots = data
        self.render_view()

    def render_view(self) -> None:
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._mode == "loading":
            lbl = QLabel("Loading screenshots...", self)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px; padding: 40px;")
            self.layout.addWidget(lbl)
        elif self._mode == "empty":
            container = QWidget(self)
            c_layout = QVBoxLayout(container)
            c_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_layout.setSpacing(8)
            c_layout.setContentsMargins(0, 30, 0, 30)

            icon = QLabel("📷", container)
            icon.setFont(QFont("Segoe UI", 32))
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_layout.addWidget(icon)

            title = QLabel("No screenshots captured yet", container)
            title.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
            title.setStyleSheet(f"color: {TEXT_PRIMARY};")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_layout.addWidget(title)

            sub = QLabel("Screenshots will appear here automatically during active tracking.", container)
            sub.setFont(QFont("Segoe UI", 12))
            sub.setStyleSheet(f"color: {TEXT_MUTED};")
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_layout.addWidget(sub)

            self.layout.addWidget(container)
        else:
            screenshots_to_show = self._screenshots if self._screenshots else MOCK_SCREENSHOTS
            grid_widget = QWidget(self)
            grid = QGridLayout(grid_widget)
            grid.setSpacing(12)
            grid.setContentsMargins(0, 0, 0, 0)

            cols = 4
            for i, shot in enumerate(screenshots_to_show):
                card = ScreenshotCard(shot, grid_widget)
                card.clicked.connect(self._open_lightbox)
                grid.addWidget(card, i // cols, i % cols)

            self.layout.addWidget(grid_widget)

    def _open_lightbox(self, shot: Dict[str, Any]) -> None:
        dlg = ScreenshotPreviewDialog(shot, self.window())
        dlg.exec()


class AppsTabView(QWidget):
    """List display of tracked apps with usage percentages and loading/empty state support."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._apps = []
        self._mode = "data"
        self._build_ui()

    def _build_ui(self) -> None:
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.render_view()

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.render_view()

    def set_data(self, data: List[Dict[str, Any]]) -> None:
        self._apps = data
        self.render_view()

    def render_view(self) -> None:
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._mode == "loading":
            lbl = QLabel("Loading application usage metrics...", self)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px; padding: 40px;")
            self.layout.addWidget(lbl)
        elif self._mode == "empty":
            container = QWidget(self)
            c_layout = QVBoxLayout(container)
            c_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_layout.setSpacing(8)
            c_layout.setContentsMargins(0, 30, 0, 30)

            icon = QLabel("💻", container)
            icon.setFont(QFont("Segoe UI", 32))
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_layout.addWidget(icon)

            title = QLabel("No application activity recorded yet", container)
            title.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
            title.setStyleSheet(f"color: {TEXT_PRIMARY};")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_layout.addWidget(title)

            sub = QLabel("Start tracking time to capture desktop applications usage.", container)
            sub.setFont(QFont("Segoe UI", 12))
            sub.setStyleSheet(f"color: {TEXT_MUTED};")
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_layout.addWidget(sub)

            self.layout.addWidget(container)
        else:
            apps_to_show = self._apps if self._apps else MOCK_APPS
            list_widget = QWidget(self)
            list_layout = QVBoxLayout(list_widget)
            list_layout.setContentsMargins(0, 0, 0, 0)
            list_layout.setSpacing(10)

            for app in apps_to_show:
                row = AppRowWidget(app, parent=list_widget)
                list_layout.addWidget(row)

            self.layout.addWidget(list_widget)


class URLsTabView(QWidget):
    """List display of website URLs visited, title and favicon, with loading/empty state support."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._urls = []
        self._mode = "data"
        self._build_ui()

    def _build_ui(self) -> None:
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.render_view()

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.render_view()

    def set_data(self, data: List[Dict[str, Any]]) -> None:
        self._urls = data
        self.render_view()

    def render_view(self) -> None:
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._mode == "loading":
            lbl = QLabel("Loading website activities...", self)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px; padding: 40px;")
            self.layout.addWidget(lbl)
        elif self._mode == "empty":
            container = QWidget(self)
            c_layout = QVBoxLayout(container)
            c_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_layout.setSpacing(8)
            c_layout.setContentsMargins(0, 30, 0, 30)

            icon = QLabel("🌐", container)
            icon.setFont(QFont("Segoe UI", 32))
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_layout.addWidget(icon)

            title = QLabel("No website activity recorded yet", container)
            title.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
            title.setStyleSheet(f"color: {TEXT_PRIMARY};")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_layout.addWidget(title)

            sub = QLabel("Web activity will appear automatically once tracking starts.", container)
            sub.setFont(QFont("Segoe UI", 12))
            sub.setStyleSheet(f"color: {TEXT_MUTED};")
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_layout.addWidget(sub)

            self.layout.addWidget(container)
        else:
            urls_to_show = self._urls if self._urls else MOCK_URLS
            list_widget = QWidget(self)
            list_layout = QVBoxLayout(list_widget)
            list_layout.setContentsMargins(0, 0, 0, 0)
            list_layout.setSpacing(10)

            for url in urls_to_show:
                row = URLRowWidget(url, parent=list_widget)
                list_layout.addWidget(row)

            self.layout.addWidget(list_widget)


# ─── Main Controller Widget ───────────────────────────────────────────────────

class ActivitySection(QWidget):
    """
    Activity Section (replacing old screenshots layout).
    - Contains exact tabs: Screenshots, Apps, URLs.
    - Fully styled custom tab navigation.
    - Integrates State Controller pills in top right for review testing.
    """

    def __init__(self, api_client: ApiClient, local_cache=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.api_client = api_client
        self.local_cache = local_cache
        self._mode = "data"  # "data" | "loading" | "empty"
        self._active_tab = "screenshots"
        self._apps_worker = None
        self._screenshots_worker = None

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._build_ui()
        
        # Periodic auto-refresh timer (every 10 seconds)
        self._auto_timer = QTimer(self)
        self._auto_timer.timeout.connect(self.refresh)
        self._auto_timer.start(10000)

        self.refresh()


    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Card container (explicitly expanding size policy)
        self.card = QFrame(self)
        self.card.setObjectName("ActivityCard")
        self.card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.card.setStyleSheet(f"""
            QFrame#ActivityCard {{
                background: {CARD_BG};
                border-radius: 12px;
                border: 1px solid {BORDER_LIGHT};
            }}
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # Header Row
        header = QWidget(self.card)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 16)

        # Title container
        title_container = QWidget(header)
        title_container_layout = QHBoxLayout(title_container)
        title_container_layout.setContentsMargins(0, 0, 0, 0)
        title_container_layout.setSpacing(8)

        # Activity Pulsing-like Emoji Icon
        icon_lbl = QLabel("📈", title_container)
        icon_lbl.setFont(QFont("Segoe UI", 16))
        title_container_layout.addWidget(icon_lbl)

        self._title = QLabel("Activity", title_container)
        self._title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self._title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        title_container_layout.addWidget(self._title)

        header_layout.addWidget(title_container)
        header_layout.addStretch()

        # State Control pills widget (for testing mock states easily)
        self._state_controls = QWidget(header)
        sc_layout = QHBoxLayout(self._state_controls)
        sc_layout.setContentsMargins(4, 4, 4, 4)
        sc_layout.setSpacing(2)
        self._state_controls.setStyleSheet(f"""
            QWidget {{
                background: #F1F5F9;
                border-radius: 8px;
                border: 1px solid {BORDER_LIGHT};
            }}
        """)

        self.btn_data = QPushButton("Data", self._state_controls)
        self.btn_loading = QPushButton("Loading", self._state_controls)
        self.btn_empty = QPushButton("Empty", self._state_controls)

        for btn in [self.btn_data, self.btn_loading, self.btn_empty]:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedSize(64, 24)
            sc_layout.addWidget(btn)

        self.btn_data.clicked.connect(lambda: self.change_state("data"))
        self.btn_loading.clicked.connect(lambda: self.change_state("loading"))
        self.btn_empty.clicked.connect(lambda: self.change_state("empty"))

        header_layout.addWidget(self._state_controls)
        card_layout.addWidget(header)

        # Horizontal Divider line
        div = QFrame(self.card)
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"background: {BORDER_LIGHT}; border: none;")
        div.setFixedHeight(1)
        card_layout.addWidget(div)

        # Tabs Layout Row
        tabs_widget = QWidget(self.card)
        tabs_layout = QHBoxLayout(tabs_widget)
        tabs_layout.setContentsMargins(20, 10, 20, 10)
        tabs_layout.setSpacing(8)

        self.tab_ss = QPushButton("Screenshots", tabs_widget)
        self.tab_apps = QPushButton("Apps", tabs_widget)
        self.tab_urls = QPushButton("URLs", tabs_widget)

        for tab_btn in [self.tab_ss, self.tab_apps, self.tab_urls]:
            tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            tab_btn.setFixedHeight(34)
            tab_btn.setFlat(True)
            tabs_layout.addWidget(tab_btn)

        tabs_layout.addStretch()

        self.tab_ss.clicked.connect(lambda: self.switch_tab("screenshots"))
        self.tab_apps.clicked.connect(lambda: self.switch_tab("apps"))
        self.tab_urls.clicked.connect(lambda: self.switch_tab("urls"))

        card_layout.addWidget(tabs_widget)

        # Tabs Inner Content area
        self._scroll_area = QScrollArea(self.card)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(20, 10, 20, 20)

        # Stacked widgets to hold sub-tabs
        self.tab_stack = QStackedWidget(scroll_content)
        self.view_ss = ScreenshotsTabView(self.tab_stack)
        self.view_apps = AppsTabView(self.tab_stack)
        self.view_urls = URLsTabView(self.tab_stack)

        self.tab_stack.addWidget(self.view_ss)
        self.tab_stack.addWidget(self.view_apps)
        self.tab_stack.addWidget(self.view_urls)

        self.scroll_layout.addWidget(self.tab_stack)
        self._scroll_area.setWidget(scroll_content)
        card_layout.addWidget(self._scroll_area, 1) # Set stretch to 1 to occupy all space inside card

        layout.addWidget(self.card, 1) # Set stretch to 1 to occupy all space inside parent widget

        # Apply initial active tab stylesheet
        self._update_tab_styling()
        self._update_state_button_styling()

    def _update_tab_styling(self) -> None:
        """Apply Tailwind-like active bottom border styling to QPushButtons."""
        tab_list = [
            ("screenshots", self.tab_ss),
            ("apps", self.tab_apps),
            ("urls", self.tab_urls)
        ]
        for name, btn in tab_list:
            if name == self._active_tab:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        color: {PRIMARY};
                        font-weight: bold;
                        border: none;
                        border-bottom: 2px solid {PRIMARY};
                        background: transparent;
                        padding: 0px 12px;
                        font-size: 13px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        color: {TEXT_SECONDARY};
                        font-weight: normal;
                        border: none;
                        border-bottom: 2px solid transparent;
                        background: transparent;
                        padding: 0px 12px;
                        font-size: 13px;
                    }}
                    QPushButton:hover {{
                        color: {TEXT_PRIMARY};
                        background: rgba(0, 0, 0, 0.02);
                        border-radius: 4px;
                    }}
                """)

    def _update_state_button_styling(self) -> None:
        state_list = [
            ("data", self.btn_data),
            ("loading", self.btn_loading),
            ("empty", self.btn_empty)
        ]
        for mode, btn in state_list:
            if mode == self._mode:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: #FFFFFF;
                        color: {PRIMARY};
                        border: 1px solid {BORDER_LIGHT};
                        border-radius: 6px;
                        font-weight: bold;
                        font-size: 11px;
                    }}
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: #64748B;
                        border: none;
                        border-radius: 6px;
                        font-weight: normal;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        color: #0F172A;
                    }
                """)

    def switch_tab(self, tab_name: str) -> None:
        self._active_tab = tab_name
        self._update_tab_styling()

        if tab_name == "screenshots":
            self.tab_stack.setCurrentWidget(self.view_ss)
        elif tab_name == "apps":
            self.tab_stack.setCurrentWidget(self.view_apps)
        elif tab_name == "urls":
            self.tab_stack.setCurrentWidget(self.view_urls)

    def closeEvent(self, event) -> None:
        if hasattr(self, "_auto_timer") and self._auto_timer:
            self._auto_timer.stop()
        if self._apps_worker and self._apps_worker.isRunning():
            self._apps_worker.cancel()
            self._apps_worker.wait(500)
        if self._screenshots_worker and self._screenshots_worker.isRunning():
            self._screenshots_worker.cancel()
            self._screenshots_worker.wait(500)
        super().closeEvent(event)

    def change_state(self, mode: str) -> None:
        self._mode = mode
        self._update_state_button_styling()
        
        # Propagate mode to all tabs
        self.view_ss.set_mode(mode)
        self.view_apps.set_mode(mode)
        self.view_urls.set_mode(mode)

    def refresh(self) -> None:
        """Fetch live application usage and screenshot data from backend and local cache."""
        from ui.workers import LoadAppUsageWorker, LoadScreenshotsWorker

        apps_w = getattr(self, "_apps_worker", None)
        if not apps_w or not apps_w.isRunning():
            self._apps_worker = LoadAppUsageWorker(self.api_client, getattr(self, "local_cache", None), parent=self)
            def on_apps_loaded(apps_data: list):
                self.view_apps.set_data(apps_data)
                self.view_apps.set_mode("data")
            self._apps_worker.finished.connect(on_apps_loaded)
            self._apps_worker.start()

        shots_w = getattr(self, "_screenshots_worker", None)
        if not shots_w or not shots_w.isRunning():
            self._screenshots_worker = LoadScreenshotsWorker(self.api_client, parent=self)
            def on_shots_loaded(shots_data: list):
                self.view_ss.set_data(shots_data)
                self.view_ss.set_mode("data")
            self._screenshots_worker.finished.connect(on_shots_loaded)
            self._screenshots_worker.start()


