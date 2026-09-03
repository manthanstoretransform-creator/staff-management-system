"""
Sidebar — dark navy collapsible sidebar with Monitra branding,
real project list with pagination & search, live total-time-today, and user card.
"""
import math
from datetime import datetime
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtGui import QFont, QColor, QPainter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QSizePolicy, QSpacerItem,
    QMenu, QStackedWidget, QToolButton, QProxyStyle, QStyle
)
from core.time_format import format_hms
from ui import icons
from core.branding import logo_pixmap
from ui.styles import (
    SIDEBAR_BG, SIDEBAR_BG_HOVER, SIDEBAR_SELECTED, SIDEBAR_MUTED,
    SIDEBAR_TEXT, SIDEBAR_BORDER, PROJECT_COLORS, SUCCESS, TEXT_MUTED,
    BRAND_BLUE, PRIMARY,
)

EXPANDED_WIDTH = 300
COLLAPSED_WIDTH = 60

# Logo mark + wordmark sizing
LOGO_MARK_SIZE_EXPANDED = 44
LOGO_MARK_SIZE_COLLAPSED = 36
WORDMARK_FONT_SIZE = 25
HEADER_HEIGHT_EXPANDED = 70
HEADER_HEIGHT_COLLAPSED = 96

# Total Time Today hero text sizing
TIME_DISPLAY_FONT_SIZE = 36
STATUS_FONT_SIZE = 12

# Projects pagination size
PROJECTS_PER_PAGE = 10

#: Minimum width of the account drop-down. Qt sizes a menu to its longest
#: label, which left three short actions in a cramped popup under a 300px
#: card; this gives it room to read as part of the account panel.
USER_MENU_MIN_WIDTH = 240

#: The account menu's Feedback entry. The ampersand is doubled because Qt
#: reads a single `&` in an action's text as a keyboard mnemonic and eats it:
#: the menu rendered "Feedback  Help" with the character simply missing.
FEEDBACK_MENU_LABEL = "Feedback && Help"

#: Icon size in the account drop-down. A QMenu draws action icons at the
#: style's PM_SmallIconSize -- 16px -- regardless of how large a pixmap the
#: QIcon holds, and `QMenu::icon { width/height }` in a stylesheet is
#: ignored. Overriding the metric for this one menu (see _MenuIconStyle) is
#: the supported way to make them legible.
USER_MENU_ICON_SIZE = 26


class _MenuIconStyle(QProxyStyle):
    """Draws one menu's action icons larger than the platform default."""

    def __init__(self, icon_size: int) -> None:
        super().__init__()
        self._icon_size = icon_size

    def pixelMetric(self, metric, option=None, widget=None) -> int:  # noqa: N802
        if metric == QStyle.PixelMetric.PM_SmallIconSize:
            return self._icon_size
        return super().pixelMetric(metric, option, widget)



#: The one authoritative duration formatter (core.time_format.format_hms).
#: Widgets must not keep private copies of duration formatting.
_format_seconds = format_hms


# ─── Project Item Button ─────────────────────────────────────────────────────

class ProjectItem(QPushButton):
    """A sidebar project entry with colored dot, truncated name, and tooltip."""

    def __init__(
        self,
        project: Dict[str, Any],
        color: str,
        collapsed: bool,
        has_active_timer: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.project_data = project
        self.project_color = color
        self._collapsed = collapsed
        self._has_active_timer = has_active_timer
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_tooltip()
        self._apply_style()

    def _update_tooltip(self) -> None:
        name = self.project_data.get("project_name", "")
        self.setToolTip(f"{name} — timer running" if self._has_active_timer else name)

    def set_active_timer(self, active: bool) -> None:
        """Toggle the running-timer indicator without rebuilding the row."""
        if active == self._has_active_timer:
            return
        self._has_active_timer = active
        self._update_tooltip()
        self.update()

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 8px;
                text-align: left;
                padding: 0;
                color: {SIDEBAR_TEXT};
            }}
            QPushButton:hover {{
                background: {SIDEBAR_BG_HOVER};
            }}
            QPushButton:checked {{
                background: {SIDEBAR_SELECTED};
            }}
        """)

    def paintEvent(self, event) -> None:
        """Custom paint: colored dot + elided project name + chevron (if expanded)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        if self._collapsed:
            dot_x = w // 2
            dot_y = h // 2
            dot_r = 5

            # Centered hover/selected pill in collapsed mode
            if self.isChecked():
                painter.setBrush(QColor(SIDEBAR_SELECTED))
            elif self.underMouse():
                painter.setBrush(QColor(SIDEBAR_BG_HOVER))
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)

            if self.isChecked() or self.underMouse():
                rect_w = 40
                rect_h = 36
                rect_x = (w - rect_w) // 2
                rect_y = (h - rect_h) // 2
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(rect_x, rect_y, rect_w, rect_h, 8, 8)

            # Colored indicator dot
            painter.setBrush(QColor(self.project_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(dot_x - dot_r, dot_y - dot_r, dot_r * 2, dot_r * 2)

            if self._has_active_timer:
                # Small timer badge at the dot's corner -- visible even in
                # the 60px collapsed rail.
                badge = icons.pixmap("timer", SUCCESS, 12)
                painter.drawPixmap(dot_x + dot_r - 2, dot_y + dot_r - 4, badge)

        else:
            # Background
            if self.isChecked():
                painter.setBrush(QColor(SIDEBAR_SELECTED))
            elif self.underMouse():
                painter.setBrush(QColor(SIDEBAR_BG_HOVER))
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(0, 0, w, h, 8, 8)

            dot_x = 14
            dot_y = h // 2
            dot_r = 5

            # Colored indicator dot
            painter.setBrush(QColor(self.project_color))
            painter.drawEllipse(dot_x - dot_r, dot_y - dot_r, dot_r * 2, dot_r * 2)

            name = self.project_data.get("project_name", "Unnamed")

            # Project name with right-truncation (ellipsis)
            name_font = QFont("Segoe UI", 11, QFont.Weight.DemiBold)
            painter.setFont(name_font)
            painter.setPen(QColor(SIDEBAR_TEXT))

            text_x = dot_x + dot_r + 10
            chev_w = 20
            timer_w = 20 if self._has_active_timer else 0
            max_text_w = max(10, w - text_x - chev_w - timer_w - 6)

            fm = painter.fontMetrics()
            elided_name = fm.elidedText(name, Qt.TextElideMode.ElideRight, max_text_w)

            painter.drawText(
                text_x, 0, max_text_w, h,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                elided_name
            )

            if self._has_active_timer:
                # Running-timer indicator, trailing the name and leading the
                # chevron -- reserved space above keeps it from overlapping
                # a long, elided project name.
                timer_pixmap = icons.pixmap("timer", SUCCESS, 14)
                timer_x = text_x + max_text_w + 4
                painter.drawPixmap(timer_x, (h - timer_pixmap.height()) // 2, timer_pixmap)

            # Chevron
            chev_pixmap = icons.pixmap("chevron_right", SIDEBAR_MUTED, 14)
            painter.drawPixmap(
                w - chev_w - 6 + (chev_w - chev_pixmap.width()) // 2,
                (h - chev_pixmap.height()) // 2,
                chev_pixmap,
            )

        painter.end()

    def sizeHint(self) -> QSize:
        return QSize(COLLAPSED_WIDTH if self._collapsed else EXPANDED_WIDTH - 16, 40)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self.update()

    def get_project_id(self) -> Optional[int]:
        return self.project_data.get("id")


class ElidedLabel(QLabel):
    """QLabel that elides text with an ellipsis (...) if it exceeds widget width."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        self._full_text = text
        if text:
            self.setToolTip(text)

    def setText(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        super().setText(text)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        metrics = painter.fontMetrics()
        elided = metrics.elidedText(self._full_text, Qt.TextElideMode.ElideRight, max(1, self.width()))

        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)
        painter.end()


class UserCardFrame(QFrame):
    """
    Account card at the bottom of the sidebar.
    Uses WA_StyledBackground to render stylesheet backgrounds reliably.
    """

    clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ─── Sidebar Widget ───────────────────────────────────────────────────────────

class SidebarWidget(QWidget):
    """
    Dark navy collapsible sidebar with project list pagination.
    Emits project_selected(project_dict) when a project is clicked.
    Emits logout_requested() when user clicks Sign Out.
    Emits collapse_toggled(bool) when collapse state changes.
    """
    project_selected = Signal(dict)
    logout_requested = Signal()
    collapse_toggled = Signal(bool)
    #: The footer's Refresh action. Same intent as the top bar's refresh
    #: icon: DashboardWindow re-fetches; this widget fetches nothing itself.
    refresh_requested = Signal()
    #: The footer's Feedback & Help action. The sidebar opens nothing itself;
    #: DashboardWindow owns the dialog's lifetime, exactly as it owns the idle
    #: alert's, so a transient widget never owns a window that outlives it.
    feedback_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self._collapsed = False
        self._projects: List[Dict[str, Any]] = []
        self._project_items: List[ProjectItem] = []
        self._user_info: Dict[str, Any] = {}
        self._total_seconds = 0
        self._is_active = False
        self._search_text = ""
        self._current_page = 1
        self._selected_project_id: Optional[int] = None
        self._active_timer_project_id: Optional[int] = None

        self.setFixedWidth(EXPANDED_WIDTH)
        self.setMinimumHeight(400)
        self._build_ui()
        self._apply_style()

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QWidget#Sidebar {{
                background-color: {SIDEBAR_BG};
            }}
            QWidget {{
                background-color: {SIDEBAR_BG};
                color: {SIDEBAR_TEXT};
            }}
            QLineEdit {{
                background-color: rgba(255,255,255,0.07);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                padding: 7px 10px;
                color: {SIDEBAR_TEXT};
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: rgba(255,255,255,0.25);
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                width: 4px;
                background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,0.2);
                border-radius: 2px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header (logo + collapse button) ───────────────────────
        self._header_widget = QWidget(self)
        self._header_widget.setFixedHeight(HEADER_HEIGHT_EXPANDED)
        self._header_layout = QGridLayout(self._header_widget)
        self._header_layout.setContentsMargins(12, 0, 12, 0)
        self._header_layout.setHorizontalSpacing(10)
        self._header_layout.setVerticalSpacing(4)

        # Brand mark. ui/branding.py resolves it: a real logo file dropped
        # into ui/assets/ wins, otherwise the vendored vector mark is drawn.
        self._logo_mark = QLabel(self)
        self._logo_mark.setStyleSheet("background: transparent;")
        self._set_logo_size(LOGO_MARK_SIZE_EXPANDED)

        # Wordmark
        self._wordmark = QLabel("Monitra", self)
        self._wordmark.setFont(QFont("Segoe UI", WORDMARK_FONT_SIZE, QFont.Weight.Black))
        self._wordmark.setStyleSheet(
            f"color: {SIDEBAR_TEXT}; letter-spacing: -0.5px; "
            f"font-size: {WORDMARK_FONT_SIZE}pt; font-weight: 900;"
        )

        # Collapse button
        self._collapse_icon_collapsed = icons.icon("keyboard_double_arrow_right", SIDEBAR_TEXT)
        self._collapse_icon_expanded = icons.icon("keyboard_double_arrow_left", SIDEBAR_TEXT)
        self._collapse_btn = QPushButton(self)
        self._collapse_btn.setIcon(self._collapse_icon_expanded)
        self._collapse_btn.setIconSize(QSize(18, 18))
        self._collapse_btn.setFixedSize(28, 28)
        self._collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._collapse_btn.setToolTip("Collapse sidebar")
        self._collapse_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.07);
                border: none; border-radius: 6px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.14);
            }}
        """)
        self._collapse_btn.clicked.connect(self.toggle_collapse)

        # Initial layout: horizontal row
        self._header_layout.addWidget(self._logo_mark, 0, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self._header_layout.addWidget(self._wordmark, 0, 1, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self._header_layout.addWidget(self._collapse_btn, 0, 2, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

        layout.addWidget(self._header_widget)

        # Hidden dividers
        self._divider_1 = self._make_divider()
        self._divider_1.hide()

        # ── Total Time Today ───────────────────────────────────────
        self._time_section = QWidget(self)
        ts_layout = QVBoxLayout(self._time_section)
        ts_layout.setContentsMargins(18, 16, 18, 16)
        ts_layout.setSpacing(6)

        total_label = QLabel("Total Time Today", self._time_section)
        total_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        total_label.setStyleSheet(f"color: {SIDEBAR_MUTED}; letter-spacing: 1.2px; text-transform: uppercase;")
        ts_layout.addWidget(total_label)

        self._time_display = QLabel("00:00:00", self._time_section)
        self._time_display.setFont(QFont("Segoe UI", TIME_DISPLAY_FONT_SIZE, QFont.Weight.Black))
        self._time_display.setStyleSheet(
            f"color: {SIDEBAR_TEXT}; letter-spacing: 0.5px; padding: 4px 0; "
            f"font-size: {TIME_DISPLAY_FONT_SIZE}pt; font-weight: 900;"
        )
        ts_layout.addWidget(self._time_display)

        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        status_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self._status_dot = QLabel(self._time_section)
        self._status_dot.setPixmap(icons.pixmap("circle_filled", SIDEBAR_MUTED, 10))
        self._status_dot.setStyleSheet("background: transparent;")
        self._status_text = QLabel("Idle", self._time_section)
        self._status_text.setFont(QFont("Segoe UI", STATUS_FONT_SIZE, QFont.Weight.Bold))
        self._status_text.setStyleSheet(
            f"color: {SIDEBAR_MUTED}; font-size: {STATUS_FONT_SIZE}pt; font-weight: 900;"
        )

        status_row.addWidget(self._status_dot)
        status_row.addWidget(self._status_text)
        status_row.addStretch()
        ts_layout.addLayout(status_row)

        layout.addWidget(self._time_section)

        self._divider_2 = self._make_divider()
        self._divider_2.hide()

        # ── Project search ─────────────────────────────────────────
        self._search_section = QWidget(self)
        search_layout = QVBoxLayout(self._search_section)
        search_layout.setContentsMargins(12, 10, 12, 6)
        search_layout.setSpacing(0)

        self._search_input = QLineEdit(self._search_section)
        self._search_input.setPlaceholderText("Search projects...")
        self._search_input.setFixedHeight(34)
        icons.line_edit_icon_action(self._search_input, "search", SIDEBAR_MUTED)
        self._search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self._search_input)
        layout.addWidget(self._search_section)

        # ── Projects Header Bar with Pagination Controls ───────────
        self._projects_header_widget = QWidget(self)
        ph_layout = QHBoxLayout(self._projects_header_widget)
        ph_layout.setContentsMargins(16, 4, 16, 4)
        ph_layout.setSpacing(6)

        self._projects_header_label = QLabel("PROJECTS", self._projects_header_widget)
        self._projects_header_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._projects_header_label.setStyleSheet(f"color: {SIDEBAR_MUTED}; letter-spacing: 1.5px;")
        ph_layout.addWidget(self._projects_header_label)

        ph_layout.addStretch()

        # Pagination controls container
        self._pagination_widget = QWidget(self._projects_header_widget)
        pag_layout = QHBoxLayout(self._pagination_widget)
        pag_layout.setContentsMargins(0, 0, 0, 0)
        pag_layout.setSpacing(4)

        btn_style = f"""
            QPushButton {{
                background: rgba(255,255,255,0.07);
                border: none;
                border-radius: 4px;
                color: {SIDEBAR_TEXT};
                font-size: 10px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.18);
            }}
            QPushButton:disabled {{
                color: rgba(255,255,255,0.2);
                background: transparent;
            }}
        """

        self._prev_page_btn = QPushButton(self._pagination_widget)
        self._prev_page_btn.setIcon(icons.icon("chevron_left", SIDEBAR_TEXT, 14))
        self._prev_page_btn.setFixedSize(20, 20)
        self._prev_page_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prev_page_btn.setStyleSheet(btn_style)
        self._prev_page_btn.clicked.connect(self._prev_page)
        pag_layout.addWidget(self._prev_page_btn)

        self._page_label = QLabel("1/1", self._pagination_widget)
        self._page_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._page_label.setStyleSheet(f"color: {SIDEBAR_MUTED};")
        pag_layout.addWidget(self._page_label)

        self._next_page_btn = QPushButton(self._pagination_widget)
        self._next_page_btn.setIcon(icons.icon("chevron_right", SIDEBAR_TEXT, 14))
        self._next_page_btn.setFixedSize(20, 20)
        self._next_page_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_page_btn.setStyleSheet(btn_style)
        self._next_page_btn.clicked.connect(self._next_page)
        pag_layout.addWidget(self._next_page_btn)

        ph_layout.addWidget(self._pagination_widget)
        layout.addWidget(self._projects_header_widget)

        # ── Project list ───────────────────────────────────────────
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._scroll_content = QWidget()
        self._scroll_content.setStyleSheet(f"background: {SIDEBAR_BG};")
        self._projects_layout = QVBoxLayout(self._scroll_content)
        self._projects_layout.setContentsMargins(8, 4, 8, 8)
        self._projects_layout.setSpacing(2)
        self._projects_layout.addStretch()

        self._scroll_area.setWidget(self._scroll_content)

        # ── Projects content area ──────────────────────────────────
        #
        # The one flexible region of the sidebar. The project list and the
        # empty state are two pages of the *same* container, so they occupy
        # identical geometry and switching between them cannot move anything
        # below.
        #
        # They used to be siblings in this layout -- the scroll area carrying
        # the only stretch factor, the empty label carrying none -- and
        # `_rebuild_project_list` swapped them with show()/hide(). Hiding the
        # scroll area removed the only widget that claimed the leftover
        # vertical space, so Qt shared it out among whichever remaining
        # widgets had a growable size policy. That is what lifted the account
        # card and opened a gap beneath it whenever the project count hit
        # zero.
        self._projects_area = QStackedWidget(self)
        self._projects_area.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        self._projects_area.addWidget(self._scroll_area)          # page 0: list

        self._empty_page = QWidget(self._projects_area)
        self._empty_page.setStyleSheet(f"background: {SIDEBAR_BG};")
        empty_layout = QVBoxLayout(self._empty_page)
        empty_layout.setContentsMargins(16, 12, 16, 12)
        empty_layout.setSpacing(0)
        # Centred within whatever height the area happens to have, rather
        # than sized to its own text.
        empty_layout.addStretch(1)
        self._empty_label = QLabel("No projects found", self._empty_page)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setStyleSheet(
            f"color: {SIDEBAR_MUTED}; font-size: 12px; background: transparent;"
        )
        empty_layout.addWidget(self._empty_label)
        empty_layout.addStretch(1)
        self._projects_area.addWidget(self._empty_page)           # page 1: empty

        layout.addWidget(self._projects_area, 1)

        layout.addWidget(self._make_divider())

        # ── User Card ──────────────────────────────────────────────
        self._user_card = UserCardFrame(self)
        self._user_card.setFixedHeight(60)
        self._user_card.setCursor(Qt.CursorShape.PointingHandCursor)
        self._user_card.setObjectName("UserCard")
        self._user_card.clicked.connect(self._show_user_menu)

        self._user_layout = QHBoxLayout(self._user_card)
        self._user_layout.setContentsMargins(12, 8, 12, 8)
        self._user_layout.setSpacing(10)

        # Avatar circle
        self._avatar_label = QLabel("?", self._user_card)
        self._avatar_label.setFixedSize(36, 36)
        self._avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._avatar_label.setStyleSheet(
            "background: #2563EB; color: white; border-radius: 18px;"
        )
        self._user_layout.addWidget(self._avatar_label)

        # User info container
        self._user_info_widget = QWidget(self._user_card)
        self._user_info_widget.setStyleSheet("background: transparent;")
        user_text_col = QVBoxLayout(self._user_info_widget)
        user_text_col.setContentsMargins(0, 0, 0, 0)
        user_text_col.setSpacing(1)

        self._user_name_label = ElidedLabel("User", self._user_info_widget)
        self._user_name_label.setObjectName("UserName")
        self._user_name_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        user_text_col.addWidget(self._user_name_label)

        self._user_email_label = ElidedLabel("", self._user_info_widget)
        self._user_email_label.setObjectName("UserEmail")
        self._user_email_label.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        user_text_col.addWidget(self._user_email_label)

        self._user_layout.addWidget(self._user_info_widget, 1)

        self._chevron_label = QLabel(self._user_card)
        self._chevron_label.setObjectName("UserChevron")
        self._chevron_label.setPixmap(icons.pixmap("expand_more", SIDEBAR_MUTED, 16))
        self._user_layout.addWidget(self._chevron_label)

        self._user_card.setStyleSheet(f"""
            QFrame#UserCard {{
                background: {SIDEBAR_BG};
                border: none;
                border-top: 1px solid {SIDEBAR_BORDER};
                border-radius: 0px;
            }}
            QFrame#UserCard:hover {{
                background: {SIDEBAR_BG_HOVER};
                border-top: 1px solid {SIDEBAR_BORDER};
            }}
            QFrame#UserCard:pressed {{
                background: {SIDEBAR_BG_HOVER};
                border-top: 1px solid {SIDEBAR_BORDER};
            }}
            QLabel#UserName, QLabel#UserEmail, QLabel#UserChevron {{
                background: transparent;
                color: {SIDEBAR_TEXT};
                border: none;
            }}
            QLabel#UserEmail {{
                color: {SIDEBAR_MUTED};
            }}
            QLabel#UserChevron {{
                color: {SIDEBAR_MUTED};
            }}
        """)

        layout.addWidget(self._user_card)

        # ── Last sync time ─────────────────────────────────────────
        # Purely a readout of SyncService.last_synced_at, published via its
        # synced_at_changed signal -- never a locally-counted or fabricated
        # value. Shows an honest "Never" until the first sync actually
        # completes this session.
        self._sync_row = QWidget(self)
        self._sync_row.setStyleSheet("background: transparent;")
        sync_row_layout = QHBoxLayout(self._sync_row)
        sync_row_layout.setContentsMargins(8, 6, 8, 8)
        sync_row_layout.setSpacing(8)
        sync_row_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._last_sync_label = QLabel("Last sync: —", self._sync_row)
        self._last_sync_label.setObjectName("LastSyncLabel")
        self._last_sync_label.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        self._last_sync_label.setStyleSheet(f"color: {SIDEBAR_MUTED}; background: transparent;")
        sync_row_layout.addWidget(self._last_sync_label)

        # Manual refresh, next to the timestamp it refreshes. It emits the
        # same request the top bar's refresh icon does -- DashboardWindow's
        # refresh_data() -- rather than reaching for data itself.
        self._refresh_btn = QPushButton(" Refresh", self._sync_row)
        self._refresh_btn.setObjectName("SidebarRefreshBtn")
        self._refresh_btn.setIcon(icons.icon("refresh", BRAND_BLUE, 13))
        self._refresh_btn.setIconSize(QSize(13, 13))
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.setFlat(True)
        self._refresh_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._refresh_btn.setStyleSheet(f"""
            QPushButton#SidebarRefreshBtn {{
                background: transparent; border: none;
                color: {BRAND_BLUE}; padding: 2px 4px;
            }}
            QPushButton#SidebarRefreshBtn:hover {{ color: #FFFFFF; }}
        """)
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)
        sync_row_layout.addWidget(self._refresh_btn)

        layout.addWidget(self._sync_row)

        # Only the projects area may take leftover vertical space. Every other
        # section is pinned to its own height, so a short project list cannot
        # be compensated for by inflating the sections around it -- which is
        # how the gap under the account card appeared. Declared here, once,
        # after the whole column exists, rather than scattered through the
        # builders.
        for fixed in (
            self._header_widget, self._time_section, self._search_section,
            self._projects_header_widget, self._user_card, self._sync_row,
        ):
            fixed.setSizePolicy(
                fixed.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Fixed
            )

    def _set_logo_size(self, size: int) -> None:
        """Render the brand mark at `size`, square, without upscaling a
        smaller bitmap -- branding.logo_pixmap draws at the size asked for."""
        self._logo_mark.setFixedSize(size, size)
        self._logo_mark.setPixmap(logo_pixmap(size))

    def _make_divider(self) -> QFrame:
        line = QFrame(self)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {SIDEBAR_BORDER}; border: none;")
        return line

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_user(self, user_info: Dict[str, Any]) -> None:
        """Populate user card from session data."""
        self._user_info = user_info
        name = user_info.get("name", user_info.get("username", "User"))
        email = user_info.get("email", "")
        initials = "".join(p[0].upper() for p in name.split()[:2]) if name else "?"

        self._avatar_label.setText(initials)
        self._user_name_label.setText(name)
        self._user_email_label.setText(email)

        # Set tooltip showing full name and full email on user card & labels
        full_tooltip = f"{name}\n{email}" if email else name
        self._user_card.setToolTip(full_tooltip)
        self._avatar_label.setToolTip(full_tooltip)
        self._user_name_label.setToolTip(name)
        self._user_email_label.setToolTip(email)

        self._user_info_widget.setVisible(not self._collapsed)
        self._chevron_label.setVisible(not self._collapsed)

    def set_projects_message(self, message: str) -> None:
        """
        Show a message where the project list would be.

        Every non-list state -- no projects, no search matches, loading,
        a failed load -- renders through this one call, on the empty page of
        the projects area. That is what keeps the account card and the sync
        footer still: the message occupies the same rectangle the list does,
        so nothing below it can be displaced by the text's own height.
        """
        self._empty_label.setText(message)
        self._projects_area.setCurrentWidget(self._empty_page)
        self._pagination_widget.hide()

    def set_projects(self, projects: List[Dict[str, Any]]) -> None:
        """Rebuild the project list from real API data."""
        self._projects = projects
        self._current_page = 1
        self._rebuild_project_list()

    def set_total_seconds(self, total: int) -> None:
        self._total_seconds = total
        self._time_display.setText(_format_seconds(self._total_seconds))

    def set_last_synced_at(self, when: Optional[datetime]) -> None:
        """Render the last successful sync time, or an honest empty state.

        :param when: UTC datetime from SyncService.last_synced_at /
            synced_at_changed. None means no sync has completed yet this
            session -- never rendered as a fabricated timestamp.
        """
        if when is None:
            self._last_sync_label.setText("Last sync: Never")
            return
        local = when.astimezone() if when.tzinfo else when
        self._last_sync_label.setText(f"Last sync: {local.strftime('%d-%m-%Y %H:%M:%S')}")

    def set_timer_active(self, active: bool) -> None:
        self._is_active = active
        if active:
            self._status_dot.setPixmap(icons.pixmap("circle_filled", SUCCESS, 10))
            self._status_text.setStyleSheet(
                f"color: {SUCCESS}; font-size: {STATUS_FONT_SIZE}pt; font-weight: 900;"
            )
            self._status_text.setText("Active")
        else:
            self._status_dot.setPixmap(icons.pixmap("circle_filled", SIDEBAR_MUTED, 10))
            self._status_text.setStyleSheet(
                f"color: {SIDEBAR_MUTED}; font-size: {STATUS_FONT_SIZE}pt; font-weight: 900;"
            )
            self._status_text.setText("Idle")

    def select_project(self, project_id: int) -> None:
        self._selected_project_id = project_id

        # Check if target project is on a different page
        filtered = [
            p for p in self._projects
            if self._search_text.lower() in p.get("project_name", "").lower()
        ]
        target_page = 1
        for idx, p in enumerate(filtered):
            if p.get("id") == project_id:
                target_page = (idx // PROJECTS_PER_PAGE) + 1
                break

        if target_page != self._current_page:
            self._current_page = target_page
            self._rebuild_project_list()
        else:
            for item in self._project_items:
                item.setChecked(item.get_project_id() == project_id)

    def set_active_timer_project(self, project_id: Optional[int]) -> None:
        """Update which project shows the running-timer indicator.

        Reflects the TimerService's actual state via DashboardWindow -- this
        widget makes no timer decisions of its own, only renders what it's told.
        """
        if project_id == self._active_timer_project_id:
            return
        self._active_timer_project_id = project_id
        for item in self._project_items:
            item.set_active_timer(item.get_project_id() == project_id)

    def toggle_collapse(self) -> None:
        self._collapsed = not self._collapsed
        self._apply_collapse_state()
        self.collapse_toggled.emit(self._collapsed)

    # ── Private helpers ────────────────────────────────────────────────────────

    def _prev_page(self) -> None:
        if self._current_page > 1:
            self._current_page -= 1
            self._rebuild_project_list()

    def _next_page(self) -> None:
        filtered = [
            p for p in self._projects
            if self._search_text.lower() in p.get("project_name", "").lower()
        ]
        total_pages = max(1, math.ceil(len(filtered) / PROJECTS_PER_PAGE))
        if self._current_page < total_pages:
            self._current_page += 1
            self._rebuild_project_list()

    def _rebuild_project_list(self) -> None:
        self._projects_header_label.setText(f"PROJECTS ({len(self._projects)})")

        for item in self._project_items:
            self._projects_layout.removeWidget(item)
            item.deleteLater()
        self._project_items.clear()

        filtered = [
            p for p in self._projects
            if self._search_text.lower() in p.get("project_name", "").lower()
        ]

        total_pages = max(1, math.ceil(len(filtered) / PROJECTS_PER_PAGE))
        self._current_page = max(1, min(self._current_page, total_pages))

        start_idx = (self._current_page - 1) * PROJECTS_PER_PAGE
        page_projects = filtered[start_idx : start_idx + PROJECTS_PER_PAGE]

        if not filtered:
            # Same container, different page -- nothing below this moves.
            # The message distinguishes "you have no projects" from "your
            # search matched none of them", which are different facts.
            self.set_projects_message(
                "No projects match your search" if self._search_text
                else "No projects found"
            )
            self._pagination_widget.hide()
        else:
            self._projects_area.setCurrentWidget(self._scroll_area)

            if total_pages > 1 and not self._collapsed:
                self._pagination_widget.show()
                self._page_label.setText(f"{self._current_page}/{total_pages}")
                self._prev_page_btn.setEnabled(self._current_page > 1)
                self._next_page_btn.setEnabled(self._current_page < total_pages)
            else:
                self._pagination_widget.hide()

        for i, project in enumerate(page_projects):
            global_idx = start_idx + i
            color = PROJECT_COLORS[global_idx % len(PROJECT_COLORS)]
            item = ProjectItem(
                project, color, self._collapsed,
                has_active_timer=(project.get("id") == self._active_timer_project_id),
                parent=self._scroll_content,
            )
            if self._selected_project_id is not None and project.get("id") == self._selected_project_id:
                item.setChecked(True)
            item.clicked.connect(lambda checked, p=project, c=color: self._on_project_clicked(p, c))
            self._projects_layout.insertWidget(self._projects_layout.count() - 1, item)
            self._project_items.append(item)

    def _on_project_clicked(self, project: Dict[str, Any], color: str) -> None:
        pid = project.get("id")
        self._selected_project_id = pid
        for item in self._project_items:
            item.setChecked(item.get_project_id() == pid)
        self.project_selected.emit(project)

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text
        self._current_page = 1
        self._rebuild_project_list()

    def _apply_collapse_state(self) -> None:
        is_col = self._collapsed
        self.setFixedWidth(COLLAPSED_WIDTH if is_col else EXPANDED_WIDTH)

        for i in reversed(range(self._header_layout.count())):
            self._header_layout.takeAt(i)

        if is_col:
            # Collapsed mode: logo centered on top, » button centered below
            self._set_logo_size(LOGO_MARK_SIZE_COLLAPSED)
            self._header_layout.setContentsMargins(0, 14, 0, 10)
            self._header_layout.setHorizontalSpacing(0)
            self._header_layout.setVerticalSpacing(10)
            self._header_layout.addWidget(self._logo_mark, 0, 0, Qt.AlignmentFlag.AlignCenter)
            self._header_layout.addWidget(self._collapse_btn, 1, 0, Qt.AlignmentFlag.AlignCenter)
            self._wordmark.hide()
            self._header_widget.setFixedHeight(HEADER_HEIGHT_COLLAPSED)
            self._divider_1.hide()
            self._divider_2.hide()
            self._time_section.hide()
            self._search_section.hide()
            self._projects_header_widget.hide()
            self._sync_row.hide()

            self._projects_layout.setContentsMargins(0, 4, 0, 8)
            self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

            # Center avatar in user card
            self._user_info_widget.hide()
            self._chevron_label.hide()
            self._user_layout.setContentsMargins(0, 0, 0, 0)
            self._user_layout.setSpacing(0)
            self._user_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        else:
            # Expanded mode: Logo + Wordmark + « in a single row
            self._set_logo_size(LOGO_MARK_SIZE_EXPANDED)
            self._header_layout.setContentsMargins(12, 0, 12, 0)
            self._header_layout.setHorizontalSpacing(10)
            self._header_layout.setVerticalSpacing(4)
            self._header_layout.addWidget(self._logo_mark, 0, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self._header_layout.addWidget(self._wordmark, 0, 1, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self._header_layout.addWidget(self._collapse_btn, 0, 2, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
            self._wordmark.show()
            self._header_widget.setFixedHeight(HEADER_HEIGHT_EXPANDED)
            self._divider_1.hide()
            self._divider_2.hide()
            self._time_section.show()
            self._search_section.show()
            self._projects_header_widget.show()
            self._sync_row.show()

            self._projects_layout.setContentsMargins(8, 4, 8, 8)
            self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

            # Align avatar to left in user card
            self._user_info_widget.show()
            self._chevron_label.show()
            self._user_layout.setContentsMargins(12, 8, 12, 8)
            self._user_layout.setSpacing(10)
            self._user_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._collapse_btn.setIcon(self._collapse_icon_collapsed if is_col else self._collapse_icon_expanded)
        self._collapse_btn.setToolTip("Expand sidebar" if is_col else "Collapse sidebar")

        # Rebuild project items to reflect collapse state
        self._rebuild_project_list()

    def _show_user_menu(self) -> None:
        """Open the account menu and act on the chosen entry."""
        menu, feedback_action, logout_action = self._build_user_menu()
        pos = self._user_card.mapToGlobal(self._user_card.rect().topLeft())
        pos.setY(pos.y() - menu.sizeHint().height() - 4)
        action = menu.exec(pos)
        if action == logout_action:
            self.logout_requested.emit()
        elif action == feedback_action:
            self.feedback_requested.emit()

    def _build_user_menu(self):
        """Build the account menu. Split from showing it so the contents can
        be asserted without entering `QMenu.exec`'s modal loop."""
        menu = QMenu(self)
        # Held on self, not locally: QMenu does not take ownership of a style,
        # so a local reference would be collected and the menu left pointing
        # at freed memory.
        self._menu_icon_style = _MenuIconStyle(USER_MENU_ICON_SIZE)
        menu.setStyle(self._menu_icon_style)
        # Wider and taller than Qt's default sizing for three short labels:
        # the menu carries the account's actions and looked cramped against
        # the 300px card it drops out of.
        menu.setMinimumWidth(USER_MENU_MIN_WIDTH)
        menu.setStyleSheet(f"""
            QMenu {{
                background: #1E2D47;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 10px;
                padding: 8px;
                color: {SIDEBAR_TEXT};
            }}
            QMenu::item {{
                padding: 12px 22px;
                border-radius: 8px;
                font-size: 14px;
                min-width: {USER_MENU_MIN_WIDTH - 70}px;
            }}
            QMenu::icon {{
                left: 10px;
            }}
            QMenu::item:selected {{
                background: rgba(255,255,255,0.08);
            }}
            QMenu::separator {{
                height: 1px;
                background: rgba(255,255,255,0.08);
                margin: 4px 8px;
            }}
        """)

        profile_action = menu.addAction(
            icons.icon("account_circle", SIDEBAR_TEXT, USER_MENU_ICON_SIZE), "Profile"
        )
        profile_action.setEnabled(False)
        # Feedback & Help takes the slot Settings held. Unlike Profile and
        # Settings it is a working action, so it is enabled.
        feedback_action = menu.addAction(
            icons.icon("feedback_help", SIDEBAR_TEXT, USER_MENU_ICON_SIZE),
            FEEDBACK_MENU_LABEL,
        )
        menu.addSeparator()
        logout_action = menu.addAction(
            icons.icon("logout", SIDEBAR_TEXT, USER_MENU_ICON_SIZE), "Sign Out"
        )
        return menu, feedback_action, logout_action