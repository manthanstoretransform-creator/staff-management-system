"""
Activity section — displays captured screenshots, active application usage,
and website URLs visited, using clean tabs and premium PySide6 UI styling.
"""
from typing import Optional, List, Dict, Any

import random

from PySide6.QtCore import Qt, QRectF, QSize, QTimer, Signal
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QGridLayout, QPushButton, QSizePolicy, QStackedWidget,
    QDialog, QProgressBar
)

from app.api.client import ApiClient
from core.logging_setup import get_logger
from core.time_format import ist_clock

log = get_logger("ui.activity")

#: A thumbnail is one small image over one round trip. The generous 30s budget
#: it used to get meant a stalled connection held a pool slot for half a minute
#: and the card sat blank the whole time; a preview that has not arrived in
#: this long is better retried than waited on.
IMAGE_TIMEOUT_SECONDS = 12.0
#: Attempts before a preview is reported unavailable. Transient failures are
#: the common case, so giving up on the first one made present screenshots look
#: missing.
IMAGE_MAX_ATTEMPTS = 3
IMAGE_RETRY_BASE_MS = 700

#: Screenshot grid geometry. The card height is fixed rather than derived,
#: because a grid row grows to whatever height it is given: with one row of
#: results the same card rendered as a tall box with a large empty area under
#: the thumbnail, and with three rows it rendered compactly. Same data, two
#: different layouts, depending only on how much the panel happened to have
#: captured that day.
SCREENSHOT_COLUMNS = 4
SCREENSHOT_THUMB_HEIGHT = 120
SCREENSHOT_CARD_HEIGHT = 184
#: Rows revealed at a time, matching the "Load more" behaviour of the Apps and
#: URLs tabs. A multiple of the column count, so a page never leaves a ragged
#: half-row above the button.
SCREENSHOT_PAGE_SIZE = SCREENSHOT_COLUMNS * 2
from ui import icons
from ui.icon_manager import IconManager, safe_open_url
from ui.styles import (
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BORDER_LIGHT, BORDER_MID, CARD_BG, CONTENT_BG, PRIMARY, SUCCESS, WARNING, ERROR
)

#: Material icon used for each Activity tab, both in the tab button itself
#: and matching the icon already shown in that tab's empty state.
_TAB_ICONS = {
    "screenshots": "screenshot_monitor",
    "apps": "apps",
    "urls": "language",
    "activity": "trending_up",
}

# ─── Custom Widgets ───────────────────────────────────────────────────────────

#: Render a backend timestamp as an IST wall clock. The one definition lives
#: in `core.time_format`, beside `to_ist`, because the card and the toast that
#: announces the same screenshot must not disagree about when it was taken.
#: These cards once formatted the backend's UTC value directly, so a capture
#: taken at 7:34 PM was labelled 2:04 PM.
_ist_clock = ist_clock


def _flatten_timeline(payload: Any) -> List[Dict[str, Any]]:
    """Turn the timeline response into one card record per screenshot.

    Each screenshot inherits the activity of the window it was captured in —
    that window's own measurement, never the day's — plus how many screenshots
    that window holds. The count comes from the response rather than being
    assumed to be one, so a future three- or five-per-window configuration
    renders correctly here with no change.
    """
    if not isinstance(payload, dict):
        return []
    cards: List[Dict[str, Any]] = []
    for window in payload.get("windows", []) or []:
        shots = window.get("screenshots") or []
        label = "%s - %s" % (
            _ist_clock(window.get("window_start")),
            _ist_clock(window.get("window_end")),
        )
        for shot in shots:
            cards.append({
                **shot,
                "activity_percent": window.get("activity_percentage", 0),
                "activity_measured_seconds": window.get("activity_measured_seconds", 0),
                "window_label": label,
                "window_screenshot_count": window.get("screenshot_count", len(shots)),
            })
    # Newest first, matching every other listing in this panel.
    cards.sort(key=lambda c: c.get("captured_at") or "", reverse=True)
    return cards


def _activity_color(percent: int) -> str:
    if percent >= 80:
        return SUCCESS
    if percent >= 50:
        return WARNING
    return ERROR


class ScreenshotThumbnail(QWidget):
    """Displays a real captured screenshot.

    It renders the image the backend stored, and nothing else. Its predecessor
    painted a gradient "simulating" a workspace -- window chrome, a sidebar,
    content cards -- which looked convincing enough that fabricated pictures
    were mistaken for the user's own screen. Presenting invented data as the
    user's own is the exact failure DO_NOT_DO.md records. Where there is no
    image, this says so in words.
    """

    def __init__(self, height: int = 120, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(height)
        self._pixmap: Optional[QPixmap] = None
        self._state = "loading"

    def set_image(self, data: bytes) -> None:
        pixmap = QPixmap()
        if not data or not pixmap.loadFromData(data):
            self.set_unavailable()
            return
        self._pixmap = pixmap
        self._state = "ready"
        self.update()

    def set_unavailable(self) -> None:
        self._pixmap = None
        self._state = "unavailable"
        self.update()

    def set_loading(self) -> None:
        self._state = "loading"
        self.update()

    @property
    def state(self) -> str:
        return self._state

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 8, 8)
        painter.setClipPath(path)
        painter.fillRect(self.rect(), QColor("#0F172A"))

        if self._state == "ready" and self._pixmap is not None:
            # Scale to fill and centre. The stored image is square and the card
            # is not, so fitting it inside would show more of the padding the
            # capture already carries than of the screen itself.
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(
                (self.width() - scaled.width()) // 2,
                (self.height() - scaled.height()) // 2,
                scaled,
            )
            return

        painter.setPen(QColor("#64748B"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "Loading preview" if self._state == "loading" else "Preview unavailable",
        )


class ScreenshotPreviewDialog(QDialog):
    """Lightbox showing one captured screenshot at full size."""

    def __init__(self, screenshot: Dict[str, Any], image: Optional[bytes] = None,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.resize(720, 560)
        self.setStyleSheet("""
            QDialog {
                background-color: #0F172A;
                border-radius: 16px;
                border: 1px solid rgba(255,255,255,0.15);
            }
        """)
        self._screenshot = screenshot
        self._image = image
        self._build_ui()

    def set_image(self, data: bytes) -> None:
        self.large_preview.set_image(data)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

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

        title_container = QWidget(header)
        tc_layout = QVBoxLayout(title_container)
        tc_layout.setContentsMargins(0, 0, 0, 0)
        tc_layout.setSpacing(2)

        captured = _ist_clock(self._screenshot.get("captured_at"))
        title_lbl = QLabel(
            "Screenshot at " + captured if captured else "Screenshot", title_container
        )
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: white; border: none; background: transparent;")

        sub_lbl = QLabel(self._screenshot.get("window_label", ""), title_container)
        sub_lbl.setFont(QFont("Segoe UI", 9))
        sub_lbl.setStyleSheet("color: #94A3B8; border: none; background: transparent;")

        tc_layout.addWidget(title_lbl)
        tc_layout.addWidget(sub_lbl)
        h_layout.addWidget(title_container)
        h_layout.addStretch()

        act_percent = int(self._screenshot.get("activity_percent", 0) or 0)
        measured = int(self._screenshot.get("activity_measured_seconds", 0) or 0)
        act_lbl = QLabel(
            (str(act_percent) + "% Activity") if measured > 0 else "Activity not measured",
            header,
        )
        act_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        act_lbl.setStyleSheet("""
            QLabel {
                background: %s;
                color: white;
                border-radius: 6px;
                padding: 4px 8px;
                border: none;
            }
        """ % (_activity_color(act_percent) if measured > 0 else "#475569"))
        h_layout.addWidget(act_lbl)

        close_btn = QPushButton(header)
        close_btn.setIcon(icons.icon("close", "#94A3B8", 14))
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

        self.large_preview = ScreenshotThumbnail(430, self)
        layout.addWidget(self.large_preview)
        if self._image:
            self.large_preview.set_image(self._image)

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

        screens = int(self._screenshot.get("window_screenshot_count", 1) or 1)
        screens_lbl = QLabel(
            str(screens) + (" screens" if screens != 1 else " screen"), footer
        )
        screens_lbl.setFont(QFont("Segoe UI", 10))
        screens_lbl.setStyleSheet("color: #94A3B8; border: none; background: transparent;")
        f_layout.addWidget(screens_lbl)
        f_layout.addStretch()

        detail = ""
        if self._screenshot.get("width") and self._screenshot.get("height"):
            detail = "%sx%s" % (self._screenshot["width"], self._screenshot["height"])
        size_bytes = self._screenshot.get("file_size_bytes")
        if size_bytes:
            detail += (" - " if detail else "") + str(round(int(size_bytes) / 1024)) + " KB"
        detail_lbl = QLabel(detail, footer)
        detail_lbl.setFont(QFont("Segoe UI", 9))
        detail_lbl.setStyleSheet("color: #64748B; border: none; background: transparent;")
        f_layout.addWidget(detail_lbl)

        layout.addWidget(footer)


class ScreenshotCard(QFrame):
    """One captured screenshot: the real image, its IST capture time, and the
    activity measured in the window it belongs to."""

    clicked = Signal(dict)

    def __init__(self, screenshot: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.screenshot = screenshot
        self.setFrameShape(QFrame.Shape.StyledPanel)
        # Fixed height, never derived from the space available: a grid row
        # stretches to fill what it is given, so the identical card rendered
        # compactly on a busy day and as a tall box with an empty area beneath
        # the thumbnail on a quiet one.
        self.setFixedHeight(SCREENSHOT_CARD_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        # A 2px border: at 1px the cards read as one continuous field rather
        # than as separate screenshots.
        self.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border-radius: 12px;
                border: 2px solid %s;
            }
            QFrame:hover {
                border-color: %s;
            }
        """ % (BORDER_MID, PRIMARY))
        self._build_ui()

    @property
    def screenshot_id(self) -> Optional[int]:
        return self.screenshot.get("id")

    def set_image(self, data: bytes) -> None:
        self.thumbnail.set_image(data)

    def set_image_unavailable(self) -> None:
        self.thumbnail.set_unavailable()

    def set_loading(self) -> None:
        self.thumbnail.set_loading()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self.thumbnail = ScreenshotThumbnail(SCREENSHOT_THUMB_HEIGHT, self)
        self.thumbnail.setCursor(Qt.CursorShape.PointingHandCursor)
        self.thumbnail.mousePressEvent = self._on_thumbnail_clicked
        layout.addWidget(self.thumbnail)

        info_row = QWidget(self)
        info_row.setStyleSheet("border: none; background: transparent;")
        info_layout = QHBoxLayout(info_row)
        info_layout.setContentsMargins(6, 0, 6, 4)
        info_layout.setSpacing(8)

        text_container = QWidget(info_row)
        tc_layout = QVBoxLayout(text_container)
        tc_layout.setContentsMargins(0, 0, 0, 0)
        tc_layout.setSpacing(1)

        window_lbl = QLabel(self.screenshot.get("window_label", ""), text_container)
        window_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        window_lbl.setStyleSheet("color: %s;" % PRIMARY)

        screens = int(self.screenshot.get("window_screenshot_count", 1) or 1)
        count_lbl = QLabel(
            str(screens) + (" screens" if screens != 1 else " screen"), text_container
        )
        count_lbl.setFont(QFont("Segoe UI", 9))
        count_lbl.setStyleSheet("color: %s;" % TEXT_SECONDARY)

        tc_layout.addWidget(window_lbl)
        tc_layout.addWidget(count_lbl)
        info_layout.addWidget(text_container, 1)
        layout.addWidget(info_row)

        # Badges overlaid on the thumbnail.
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

        ts_lbl = QLabel(_ist_clock(self.screenshot.get("captured_at")), meta_row)
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

        act_percent = int(self.screenshot.get("activity_percent", 0) or 0)
        measured = int(self.screenshot.get("activity_measured_seconds", 0) or 0)
        # "0%" and "nothing was measured in this window" are different facts.
        # Rendering the first for the second is the fabricated-metric defect in
        # miniature -- every card in an unmeasured hour read a confident 0%.
        act_lbl = QLabel(
            (str(act_percent) + "% Activity") if measured > 0 else "No activity data",
            meta_row,
        )
        act_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        act_lbl.setStyleSheet("""
            background-color: %s;
            color: white;
            border-radius: 4px;
            padding: 2px 6px;
            border: none;
        """ % (_activity_color(act_percent) if measured > 0 else "#475569"))
        meta_layout.addWidget(act_lbl)
        thumb_layout.addWidget(meta_row)

    def _on_thumbnail_clicked(self, event) -> None:
        self.clicked.emit(self.screenshot)


class UsageActivityRow(QFrame):
    """
    Unified Activity Usage Row shared between Apps Tab and URLs Tab.
    Guarantees 100% visual parity in spacing, alignment, progress bars, and metadata.
    """
    def __init__(
        self,
        item_data: Dict[str, Any],
        row_type: str = "app",  # "app" or "url"
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.item_data = item_data
        self.row_type = row_type
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
        self._load_icon()

    def _build_ui(self) -> None:
        self.setFixedHeight(68)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(14)

        # 1. Left Icon Badge (36x36px) - Vertically Centered
        letter = self.item_data.get("letter") or (self.item_data.get("name") or self.item_data.get("domain") or "A")[:2]
        color = self.item_data.get("color", PRIMARY)

        self.icon_badge = QLabel(letter[:2].upper(), self)
        self.icon_badge.setFixedSize(36, 36)
        self.icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_badge.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.icon_badge.setStyleSheet(f"""
            background-color: {color}15;
            color: {color};
            border-radius: 18px;
            border: 1.5px solid {color};
        """)
        layout.addWidget(self.icon_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        # 2. Middle Title & Subtitle + Progress Bar
        mid_container = QWidget(self)
        mid_container.setStyleSheet("border: none; background: transparent;")
        mid_layout = QVBoxLayout(mid_container)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(2)

        if self.row_type == "url":
            full_title = self.item_data.get("title") or self.item_data.get("domain", "Website")
        else:
            full_title = self.item_data.get("name") or self.item_data.get("application_name", "Application")

        # Truncate title cleanly if too long so card height stays strictly 68px
        display_title = full_title[:75] + "..." if len(full_title) > 75 else full_title
        self.title_lbl = QLabel(display_title, mid_container)
        self.title_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self.title_lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
        self.title_lbl.setToolTip(full_title)
        mid_layout.addWidget(self.title_lbl)

        # Subtitle (Clickable URL for URLs tab)
        if self.row_type == "url":
            url_text = self.item_data.get("url", "")
            display_url = url_text[:85] + "..." if len(url_text) > 85 else url_text
            self.sub_lbl = QLabel(display_url, mid_container)
            self.sub_lbl.setFont(QFont("Segoe UI", 8))
            self.sub_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            self.sub_lbl.setStyleSheet(f"""
                QLabel {{
                    color: {PRIMARY};
                    background: transparent;
                    border: none;
                }}
                QLabel:hover {{
                    text-decoration: underline;
                }}
            """)
            self.sub_lbl.setToolTip(f"Click to open: {url_text}")
            self.sub_lbl.mousePressEvent = lambda e, u=url_text: safe_open_url(u)
            mid_layout.addWidget(self.sub_lbl)
        elif self.item_data.get("subtitle"):
            sub_text = self.item_data.get("subtitle", "")
            display_sub = sub_text[:85] + "..." if len(sub_text) > 85 else sub_text
            self.sub_lbl = QLabel(display_sub, mid_container)
            self.sub_lbl.setFont(QFont("Segoe UI", 8))
            self.sub_lbl.setStyleSheet(f"color: {TEXT_MUTED};")
            mid_layout.addWidget(self.sub_lbl)

        # Usage progress bar
        pct = self.item_data.get("percentage", 0)
        self.prog_bar = QProgressBar(mid_container)
        self.prog_bar.setFixedHeight(5)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(pct)
        self.prog_bar.setStyleSheet(f"""
            QProgressBar {{
                background: #F1F5F9;
                border-radius: 2.5px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 2.5px;
            }}
        """)
        mid_layout.addWidget(self.prog_bar)
        layout.addWidget(mid_container, 1, Qt.AlignmentFlag.AlignVCenter)

        # 3. Right Metadata Block (Duration + % of total active time) - Vertically Centered
        meta_container = QWidget(self)
        meta_container.setStyleSheet("border: none; background: transparent;")
        meta_layout = QVBoxLayout(meta_container)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(2)
        meta_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        time_str = self.item_data.get("time_str") or f"{self.item_data.get('seconds', 0)}s"
        time_lbl = QLabel(time_str, meta_container)
        time_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        time_lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        pct_lbl = QLabel(f"{pct}% of total active time", meta_container)
        pct_lbl.setFont(QFont("Segoe UI", 8))
        pct_lbl.setStyleSheet(f"color: {TEXT_MUTED};")
        pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        meta_layout.addWidget(time_lbl)
        meta_layout.addWidget(pct_lbl)
        layout.addWidget(meta_container, 0, Qt.AlignmentFlag.AlignVCenter)

    def _load_icon(self) -> None:
        mgr = IconManager.instance()
        if self.row_type == "url":
            domain = self.item_data.get("domain", "")
            title = self.item_data.get("title", "")
            mgr.favicon_ready.connect(self._on_favicon_ready)
            pix = mgr.get_favicon(domain, title=title)
            if pix:
                self._apply_pixmap(pix)
        else:
            name = self.item_data.get("name") or self.item_data.get("application_name", "")
            exe_path = self.item_data.get("exe_path")
            hwnd = self.item_data.get("hwnd")
            # app_icon_ready announces the manager's own cache key, which is
            # the exe path when there is one -- comparing it against this
            # row's app name meant a resolved icon was silently dropped.
            self._icon_key = IconManager.app_icon_key(name, exe_path)
            mgr.app_icon_ready.connect(self._on_app_icon_ready)
            pix = mgr.get_app_icon(name, exe_path=exe_path, hwnd=hwnd)
            if pix:
                self._apply_pixmap(pix)

    def _on_favicon_ready(self, domain: str, pixmap: QPixmap) -> None:
        row_dom = self.item_data.get("domain", "").lower().strip()
        if row_dom == domain and pixmap and not pixmap.isNull():
            self._apply_pixmap(pixmap)

    def _on_app_icon_ready(self, key: str, pixmap: QPixmap) -> None:
        if key == getattr(self, "_icon_key", None) and pixmap and not pixmap.isNull():
            self._apply_pixmap(pixmap)

    def _apply_pixmap(self, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(26, 26, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.icon_badge.setText("")
        self.icon_badge.setPixmap(scaled)
        # A real logo keeps the same 36px tile the initials badge occupies,
        # so rows with and without a resolved icon still line up.
        self.icon_badge.setStyleSheet(
            f"border: 1px solid {BORDER_LIGHT}; background: #FFFFFF; border-radius: 10px;"
        )


class AppRowWidget(UsageActivityRow):
    """Displays a single tracked application using UsageActivityRow."""
    def __init__(self, app_data: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(item_data=app_data, row_type="app", parent=parent)


class URLRowWidget(UsageActivityRow):
    """Displays a single tracked website URL using UsageActivityRow."""
    def __init__(self, url_data: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(item_data=url_data, row_type="url", parent=parent)

# ─── Tab Sub-Views ────────────────────────────────────────────────────────────

class ScreenshotsTabView(QWidget):
    """Grid display of captures with full preview lightbox and empty/loading state support."""

    #: Emitted when a card becomes visible and needs its image fetched. The
    #: section owns the fetching, because it owns the API client and the
    #: background pool; this view only knows which images it is missing.
    image_requested = Signal(dict)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._screenshots = []
        self._mode = "data"
        #: id -> image bytes, so a re-render (a tab switch, a refresh) repaints
        #: from memory instead of re-downloading every thumbnail.
        self._images: Dict[int, bytes] = {}
        self._cards: Dict[int, "ScreenshotCard"] = {}
        self._open_dialog: Optional[ScreenshotPreviewDialog] = None
        self._visible_count = SCREENSHOT_PAGE_SIZE
        self._build_ui()

    def retry_unavailable(self) -> None:
        """Re-request every preview that gave up, and show it as loading again."""
        for shot in self._screenshots:
            shot_id = shot.get("id")
            if shot_id is None or shot_id in self._images:
                continue
            card = self._cards.get(shot_id)
            if card is not None:
                card.set_loading()
            self.image_requested.emit(shot)

    def deliver_image(self, screenshot_id: int, data: Optional[bytes]) -> None:
        """Hand a fetched image to its card (and to an open lightbox)."""
        card = self._cards.get(screenshot_id)
        if data:
            self._images[screenshot_id] = data
            if card is not None:
                card.set_image(data)
        elif card is not None:
            card.set_image_unavailable()

        dialog = self._open_dialog
        if (
            data
            and dialog is not None
            and dialog.isVisible()
            and dialog._screenshot.get("id") == screenshot_id
        ):
            dialog.set_image(data)

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
        # Keep whatever the user has already expanded to across a refresh --
        # collapsing the grid back to one page every time the panel reloads
        # would undo their "Load more" every few seconds. Mirrors the Apps and
        # URLs tabs.
        self._visible_count = min(
            max(self._visible_count, SCREENSHOT_PAGE_SIZE),
            max(len(data), SCREENSHOT_PAGE_SIZE),
        )
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

            icon = QLabel(container)
            icon.setPixmap(icons.pixmap("screenshot_monitor", TEXT_MUTED, 40))
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
            shots_to_show = self._screenshots[: self._visible_count]
            container = QWidget(self)
            outer = QVBoxLayout(container)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(12)

            grid_widget = QWidget(container)
            grid = QGridLayout(grid_widget)
            grid.setSpacing(12)
            grid.setContentsMargins(0, 0, 0, 0)
            # Every column the same width, so a part-filled last row lines up
            # with the rows above it instead of spreading to fill the space.
            for column in range(SCREENSHOT_COLUMNS):
                grid.setColumnStretch(column, 1)

            self._cards = {}
            for i, shot in enumerate(shots_to_show):
                card = ScreenshotCard(shot, grid_widget)
                card.clicked.connect(self._open_lightbox)
                grid.addWidget(card, i // SCREENSHOT_COLUMNS, i % SCREENSHOT_COLUMNS)

                shot_id = shot.get("id")
                if shot_id is None:
                    continue
                self._cards[shot_id] = card
                cached = self._images.get(shot_id)
                if cached is not None:
                    card.set_image(cached)
                else:
                    self.image_requested.emit(shot)

            outer.addWidget(grid_widget)

            remaining = len(self._screenshots) - len(shots_to_show)
            if remaining > 0:
                more = _make_load_more_button(remaining, container)
                more.clicked.connect(self._show_more)
                outer.addWidget(more, 0, Qt.AlignmentFlag.AlignHCenter)

            # Leftover height goes here, not into the cards. Without it a
            # single row of screenshots was stretched to fill the panel, so the
            # same card was compact on a busy day and a tall near-empty box on
            # a quiet one.
            outer.addStretch()
            self.layout.addWidget(container)

    def _show_more(self) -> None:
        self._visible_count += SCREENSHOT_PAGE_SIZE
        self.render_view()

    def _open_lightbox(self, shot: Dict[str, Any]) -> None:
        shot_id = shot.get("id")
        image = self._images.get(shot_id) if shot_id is not None else None
        dlg = ScreenshotPreviewDialog(shot, image, self.window())
        if image is None and shot_id is not None:
            # Not downloaded yet: ask now, and fill the lightbox in when it
            # lands rather than showing an empty frame until it is closed.
            self.image_requested.emit(shot)
        self._open_dialog = dlg
        try:
            dlg.exec()
        finally:
            self._open_dialog = None


#: How many rows each list tab shows before "Load more". The summaries can
#: run to dozens of entries; showing them all at once turns the panel into a
#: wall and makes the section's own scrollbar the only way to reach the task
#: list below it.
PAGE_SIZE = 6


def _make_load_more_button(remaining: int, parent: QWidget) -> QPushButton:
    """The list tabs' "Load more" control. It only reveals rows that are
    already loaded -- it never fetches, so it cannot fail or leave a
    spinner behind."""
    button = QPushButton(f" Load more ({remaining})", parent)
    button.setObjectName("LoadMoreBtn")
    button.setIcon(icons.icon("expand_more", TEXT_SECONDARY, 16))
    button.setIconSize(QSize(16, 16))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFixedHeight(34)
    button.setStyleSheet(f"""
        QPushButton#LoadMoreBtn {{
            background: {CONTENT_BG};
            border: 1px solid {BORDER_LIGHT};
            border-radius: 10px;
            color: {TEXT_SECONDARY};
            font-size: 12px;
            font-weight: 600;
            padding: 0 18px;
        }}
        QPushButton#LoadMoreBtn:hover {{
            border-color: {PRIMARY};
            color: {PRIMARY};
        }}
    """)
    return button


class AppsTabView(QWidget):
    """List display of tracked apps with usage percentages and loading/empty state support."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._apps = []
        self._mode = "data"
        self._visible_count = PAGE_SIZE
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
        # A refresh must not silently collapse a list the user had expanded,
        # so the reveal count is only ever reset by a smaller dataset.
        self._visible_count = min(max(self._visible_count, PAGE_SIZE), max(len(data), PAGE_SIZE))
        self.render_view()

    def _show_more(self) -> None:
        self._visible_count += PAGE_SIZE
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

            icon = QLabel(container)
            icon.setPixmap(icons.pixmap("apps", TEXT_MUTED, 40))
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
            apps_to_show = self._apps[: self._visible_count]
            list_widget = QWidget(self)
            list_layout = QVBoxLayout(list_widget)
            list_layout.setContentsMargins(0, 0, 0, 0)
            list_layout.setSpacing(8)
            list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            for app in apps_to_show:
                row = AppRowWidget(app, parent=list_widget)
                list_layout.addWidget(row)

            remaining = len(self._apps) - len(apps_to_show)
            if remaining > 0:
                more = _make_load_more_button(remaining, list_widget)
                more.clicked.connect(self._show_more)
                list_layout.addWidget(more, 0, Qt.AlignmentFlag.AlignHCenter)

            list_layout.addStretch()
            self.layout.addWidget(list_widget)


class URLsTabView(QWidget):
    """List display of website URLs visited, title and favicon, with loading/empty state support."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._urls = []
        self._mode = "data"
        self._visible_count = PAGE_SIZE
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
        self._visible_count = min(max(self._visible_count, PAGE_SIZE), max(len(data), PAGE_SIZE))
        self.render_view()

    def _show_more(self) -> None:
        self._visible_count += PAGE_SIZE
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

            icon = QLabel(container)
            icon.setPixmap(icons.pixmap("language", TEXT_MUTED, 40))
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
            urls_to_show = self._urls[: self._visible_count]
            list_widget = QWidget(self)
            list_layout = QVBoxLayout(list_widget)
            list_layout.setContentsMargins(0, 0, 0, 0)
            list_layout.setSpacing(8)
            list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            for url in urls_to_show:
                row = URLRowWidget(url, parent=list_widget)
                list_layout.addWidget(row)

            remaining = len(self._urls) - len(urls_to_show)
            if remaining > 0:
                more = _make_load_more_button(remaining, list_widget)
                more.clicked.connect(self._show_more)
                list_layout.addWidget(more, 0, Qt.AlignmentFlag.AlignHCenter)

            list_layout.addStretch()
            # Without this the list is a child of the view but belongs to no
            # layout, so Qt leaves it at its size hint in the top-left corner:
            # the rows exist and hold the right data, but appear as a small
            # empty box. Every other branch here (loading, empty, and the Apps
            # and Screenshots lists) already adds its container.
            self.layout.addWidget(list_widget)


# ─── Main Activity Section Component ───────────────────────────────────────────────────

class ActivitySection(QWidget):
    """
    Activity Section (replacing old screenshots layout).
    - Contains exact tabs: Screenshots, Apps, URLs.
    - Fully styled custom tab navigation.
    - Integrates State Controller pills in top right for review testing.
    """

    #: Auto-refresh cadence. The audited value was 10 seconds, and each tick
    #: created two fresh QThreads whether or not the previous pair had
    #: finished - six new OS threads a minute, from before the user had even
    #: logged in. Activity data does not change fast enough to justify that.
    AUTO_REFRESH_MS = 60_000

    def __init__(self, api, api_client: ApiClient, parent: Optional[QWidget] = None) -> None:
        """
        :param api: `BackgroundApi` - the only route to background work.
        :param api_client: Used to build the request callables that run on the
            shared pool. This widget never starts a thread of its own.
        """
        super().__init__(parent)
        self.api = api
        self.api_client = api_client
        self._active_tab = "screenshots"
        self._enabled = False

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._build_ui()

        # A UI-only refresh timer. It schedules work through the bounded pool
        # rather than creating threads, and it does not run until the user is
        # actually signed in.
        self._auto_timer = QTimer(self)
        self._auto_timer.timeout.connect(self.refresh)

    @property
    def local_cache(self):
        return self.api.cache

    def set_enabled(self, enabled: bool) -> None:
        """Start or stop refreshing. Called on login and logout."""
        self._enabled = enabled
        if enabled:
            self._auto_timer.start(self.AUTO_REFRESH_MS)
            self.refresh()
        else:
            self._auto_timer.stop()
            self.api.cancel_key("activity-apps")
            self.api.cancel_key("activity-screenshots")

    def set_tracking_active(self, active: bool) -> None:
        if hasattr(self, "view_act") and hasattr(self.view_act, "set_tracking_active"):
            self.view_act.set_tracking_active(active)

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

        # Header Row -- title on the left, Screenshots/Apps/URLs navigation
        # on the right, both on one line. The old testing-only Data/Loading/
        # Empty state switcher used to sit where the tabs are now; it never
        # drove real data (refresh() sets each tab's mode from actual API
        # results) and is gone entirely rather than relocated.
        header = QWidget(self.card)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 14, 16, 14)
        header_layout.setSpacing(12)

        # Title container
        title_container = QWidget(header)
        title_container_layout = QHBoxLayout(title_container)
        title_container_layout.setContentsMargins(0, 0, 0, 0)
        title_container_layout.setSpacing(8)

        # Activity icon
        icon_lbl = QLabel(title_container)
        icon_lbl.setPixmap(icons.pixmap("trending_up", PRIMARY, 18))
        title_container_layout.addWidget(icon_lbl)

        self._title = QLabel("ACTIVITY", title_container)
        self._title.setFont(QFont("Segoe UI", 10, QFont.Weight.Black))
        self._title.setStyleSheet(
            f"color: {PRIMARY}; letter-spacing: 1.2px; background: transparent;"
        )
        title_container_layout.addWidget(self._title)

        header_layout.addWidget(title_container)
        header_layout.addStretch()

        # Screenshots / Apps / URLs navigation, each with a small icon for
        # quick recognition and a Material-style underline for the active
        # state -- consistent with the task table's own tab-like controls.
        tabs_widget = QWidget(header)
        tabs_layout = QHBoxLayout(tabs_widget)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        tabs_layout.setSpacing(4)

        self.tab_ss = QPushButton(" Screenshots", tabs_widget)
        self.tab_ss.setIcon(icons.icon("screenshot_monitor", TEXT_SECONDARY, 16))
        self.tab_apps = QPushButton(" Apps", tabs_widget)
        self.tab_apps.setIcon(icons.icon("apps", TEXT_SECONDARY, 16))
        self.tab_urls = QPushButton(" URLs", tabs_widget)
        self.tab_urls.setIcon(icons.icon("language", TEXT_SECONDARY, 16))

        for tab_btn in [self.tab_ss, self.tab_apps, self.tab_urls]:
            tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            tab_btn.setFixedHeight(36)
            tab_btn.setFlat(True)
            tabs_layout.addWidget(tab_btn)

        self.tab_ss.clicked.connect(lambda: self.switch_tab("screenshots"))
        self.tab_apps.clicked.connect(lambda: self.switch_tab("apps"))
        self.tab_urls.clicked.connect(lambda: self.switch_tab("urls"))

        header_layout.addWidget(tabs_widget)
        card_layout.addWidget(header)

        # Horizontal Divider line
        div = QFrame(self.card)
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"background: {BORDER_LIGHT}; border: none;")
        div.setFixedHeight(1)
        card_layout.addWidget(div)

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
        #: screenshot id -> failed attempts so far, so a retry backs off
        #: instead of hammering a backend that is already struggling.
        self._image_attempts: Dict[int, int] = {}
        self.view_ss.image_requested.connect(self._fetch_screenshot_image)
        self.view_apps = AppsTabView(self.tab_stack)
        self.view_urls = URLsTabView(self.tab_stack)

        self.tab_stack.addWidget(self.view_ss)
        self.tab_stack.addWidget(self.view_apps)
        self.tab_stack.addWidget(self.view_urls)

        self.scroll_layout.addWidget(self.tab_stack)
        self._scroll_area.setWidget(scroll_content)
        card_layout.addWidget(self._scroll_area, 1)

        layout.addWidget(self.card, 1)

        # Apply initial active tab stylesheet
        self._update_tab_styling()

    def _update_tab_styling(self) -> None:
        """Material-style underline tabs: active tab gets the brand color
        and a bottom border indicator; inactive tabs stay muted with a
        subtle hover state."""
        tab_list = [
            ("screenshots", self.tab_ss),
            ("apps", self.tab_apps),
            ("urls", self.tab_urls),
        ]
        for name, btn in tab_list:
            if name == self._active_tab:
                btn.setIcon(icons.icon(_TAB_ICONS[name], PRIMARY, 16))
                btn.setStyleSheet(f"""
                    QPushButton {{
                        color: {PRIMARY};
                        font-weight: 600;
                        border: none;
                        border-bottom: 2.5px solid {PRIMARY};
                        background: transparent;
                        padding: 8px 14px;
                        font-size: 13px;
                        border-radius: 0px;
                    }}
                """)
            else:
                btn.setIcon(icons.icon(_TAB_ICONS[name], TEXT_SECONDARY, 16))
                btn.setStyleSheet(f"""
                    QPushButton {{
                        color: {TEXT_SECONDARY};
                        font-weight: 500;
                        border: none;
                        border-bottom: 2.5px solid transparent;
                        background: transparent;
                        padding: 8px 14px;
                        font-size: 13px;
                        border-radius: 0px;
                    }}
                    QPushButton:hover {{
                        color: {TEXT_PRIMARY};
                        background: {CONTENT_BG};
                        border-radius: 6px;
                    }}
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
        self._auto_timer.stop()
        self._enabled = False
        self.api.cancel_key("activity-apps")
        self.api.cancel_key("activity-urls")
        self.api.cancel_key("activity-screenshots")
        super().closeEvent(event)

    def refresh(self) -> None:
        """
        Refresh application usage, URLs, and screenshots.

        Requests run on the shared bounded pool and are de-duplicated by key,
        so a slow backend cannot cause overlapping requests to pile up.
        """
        if not self._enabled:
            return

        # A refresh is the user saying "try again", so previews that gave up
        # earlier get a clean slate rather than staying unavailable until the
        # tab is rebuilt.
        self.retry_failed_images()

        def load_apps():
            return self.api.app_usage_summary()

        def on_apps(apps_data: list) -> None:
            self.view_apps.set_data(apps_data)
            self.view_apps.set_mode("data" if apps_data else "empty")

        def on_apps_error(exc: BaseException) -> None:
            # Keep whatever is already on screen: a failed refresh must not
            # blank a populated panel. The attribute checked here used to be
            # "_data", which no view has, so this was always true and every
            # transient error emptied the panel.
            if not getattr(self.view_apps, "_apps", None):
                self.view_apps.set_mode("empty")

        self.api.run_in_background(
            load_apps, on_success=on_apps, on_error=on_apps_error, key="activity-apps"
        )

        def load_urls():
            return self.api.url_usage_summary()

        def on_urls(urls_data: list) -> None:
            self.view_urls.set_data(urls_data)
            self.view_urls.set_mode("data" if urls_data else "empty")

        def on_urls_error(exc: BaseException) -> None:
            if not getattr(self.view_urls, "_urls", None):
                self.view_urls.set_mode("empty")

        self.api.run_in_background(
            load_urls, on_success=on_urls, on_error=on_urls_error, key="activity-urls"
        )

        def load_shots():  # noqa: D401 - see the comment below
            # The timeline, not the bare screenshot list: it carries the
            # activity actually measured in each capture's own window, which
            # is the number the card shows. The plain listing has no activity
            # at all, so every card rendered a confident 0%.
            response = self.api_client.get("/time-entry-screenshots/timeline")
            return _flatten_timeline(response.json())

        def on_shots(shots_data: list) -> None:
            self.view_ss.set_data(shots_data)
            self.view_ss.set_mode("data" if shots_data else "empty")

        def on_shots_error(exc: BaseException) -> None:
            if not getattr(self.view_ss, "_screenshots", None):
                self.view_ss.set_mode("empty")

        self.api.run_in_background(
            load_shots, on_success=on_shots, on_error=on_shots_error, key="activity-screenshots"
        )

    def _fetch_screenshot_image(self, shot: Dict[str, Any]) -> None:
        """Download one screenshot's image on the shared pool.

        Never on the GUI thread: this is a network round trip per thumbnail.
        The de-duplication key means a card rebuilt while its image is still in
        flight does not start a second download, and the bytes are cached by
        the view, so a tab switch repaints from memory.

        The image is served by the backend, which checks the caller's
        permission on every request — the desktop never holds a Drive link.
        """
        shot_id = shot.get("id")
        view_url = shot.get("view_url")
        if shot_id is None or not view_url:
            return

        attempt = self._image_attempts.get(shot_id, 0)

        def load():
            return self.api_client.get(view_url, timeout=IMAGE_TIMEOUT_SECONDS).content

        def on_ready(data: bytes) -> None:
            self._image_attempts.pop(shot_id, None)
            self.view_ss.deliver_image(shot_id, data)

        def on_failed(exc: BaseException) -> None:
            # A thumbnail is one HTTP round trip that can lose a race with a
            # cold backend, a Drive hiccup or a sleeping laptop's first second
            # of wifi. Marking the card permanently unavailable on the first
            # such failure is what made real screenshots look missing: the
            # image was there the whole time, and nothing ever asked again.
            nonlocal attempt
            attempt += 1
            self._image_attempts[shot_id] = attempt
            if attempt >= IMAGE_MAX_ATTEMPTS:
                self.log_image_failure(shot_id, exc, attempt)
                self.view_ss.deliver_image(shot_id, None)
                return
            # Backed off, and jittered so a grid of twelve cards that all
            # failed together does not retry together.
            delay = int(IMAGE_RETRY_BASE_MS * (2 ** (attempt - 1)) * (0.5 + random.random()))
            QTimer.singleShot(delay, lambda: self._fetch_screenshot_image(shot))

        self.api.run_in_background(
            load, on_success=on_ready, on_error=on_failed, key=f"ss-image:{shot_id}"
        )

    def log_image_failure(self, shot_id: int, exc: BaseException, attempts: int) -> None:
        """Record why a preview gave up, so "it just doesn't load" is
        answerable from a log rather than only from a screenshot of the UI."""
        log.warning(
            "screenshot %s preview failed after %d attempt(s): %s",
            shot_id, attempts, exc,
        )

    def retry_failed_images(self) -> None:
        """Ask again for every preview that gave up.

        Called when the panel refreshes: a refresh is the user saying "try
        again", and the previous failure is usually long since irrelevant.
        """
        self._image_attempts.clear()
        self.view_ss.retry_unavailable()


