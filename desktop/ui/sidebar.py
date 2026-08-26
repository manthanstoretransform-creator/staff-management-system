"""
Sidebar — dark navy collapsible sidebar with Monitra branding,
real project list, live total-time-today, and user card with logout.
"""
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtGui import QFont, QColor, QPainter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QSizePolicy, QSpacerItem,
    QMenu, QToolButton
)
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import QByteArray

from ui.styles import (
    SIDEBAR_BG, SIDEBAR_BG_HOVER, SIDEBAR_SELECTED, SIDEBAR_MUTED,
    SIDEBAR_TEXT, SIDEBAR_BORDER, PROJECT_COLORS, SUCCESS, TEXT_MUTED,
    MONITRA_MARK_SVG
)

EXPANDED_WIDTH = 300  # widened again (was 300) to give the larger
                       # wordmark/time text more breathing room
COLLAPSED_WIDTH = 60

# Logo mark + wordmark sizing — large, bold and fixed, so branding stays
# readable but never resizes/reflows the rest of the sidebar UI.
LOGO_MARK_SIZE = 51
WORDMARK_FONT_SIZE = 25       # bumped again — was 30, still read small
HEADER_HEIGHT_EXPANDED = 70
HEADER_HEIGHT_COLLAPSED = 96

# "Total Time Today" is the hero number on the sidebar — make it dominant.
TIME_DISPLAY_FONT_SIZE = 36   # bumped again — was 38, still read small
STATUS_FONT_SIZE = 12


def _format_seconds(total: int) -> str:
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


# ─── Project Item Button ─────────────────────────────────────────────────────

class ProjectItem(QPushButton):
    """A sidebar project entry with colored dot, name, and tracked time."""

    def __init__(
        self,
        project: Dict[str, Any],
        color: str,
        collapsed: bool,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.project_data = project
        self.project_color = color
        self._collapsed = collapsed
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(project.get("project_name", ""))
        self._apply_style()

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
        """Custom paint: colored dot + project name + tracked time (if expanded)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        # Background
        if self.isChecked():
            painter.setBrush(QColor(SIDEBAR_SELECTED))
        elif self.underMouse():
            painter.setBrush(QColor(SIDEBAR_BG_HOVER))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, w, h, 8, 8)

        if self._collapsed:
            dot_x = w // 2
        else:
            dot_x = 14
        dot_y = h // 2
        dot_r = 5

        # Colored indicator dot
        painter.setBrush(QColor(self.project_color))
        painter.drawEllipse(dot_x - dot_r, dot_y - dot_r, dot_r * 2, dot_r * 2)

        if not self._collapsed:
            name = self.project_data.get("project_name", "Unnamed")
            # Project name
            name_font = QFont("Segoe UI", 12, QFont.Weight.DemiBold)
            painter.setFont(name_font)
            painter.setPen(QColor(SIDEBAR_TEXT))
            text_x = dot_x + dot_r + 10
            painter.drawText(text_x, 0, w - text_x - 20, h // 2 + 4, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft, name)

            # Chevron >
            painter.setPen(QColor(SIDEBAR_MUTED))
            chev_font = QFont("Segoe UI", 10)
            painter.setFont(chev_font)
            painter.drawText(w - 22, 0, 20, h, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "›")

        painter.end()

    def sizeHint(self) -> QSize:
        return QSize(EXPANDED_WIDTH if not self._collapsed else COLLAPSED_WIDTH, 44)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self.update()

    def get_project_id(self) -> Optional[int]:
        return self.project_data.get("id")


class UserCardFrame(QFrame):
    """
    Account card at the bottom of the sidebar.

    Root cause of the hover glitch: a plain QFrame does NOT paint its
    stylesheet `background` by default — Qt only respects stylesheet
    backgrounds on QFrame/QWidget subclasses once WA_StyledBackground is
    explicitly set. Without it, Qt intermittently falls back to painting
    the frame with the app/base palette (white) before repainting with
    the `:hover` rule, which is exactly the "white -> blue flash" glitch.
    Setting the attribute makes the stylesheet the single source of truth
    for this widget's background in every state (normal/hover/pressed),
    so it renders consistently instead of glitching.
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
    Dark navy collapsible sidebar.
    Emits project_selected(project_dict) when a project is clicked.
    Emits logout_requested() when user clicks Sign Out.
    Emits collapse_toggled(bool) when collapse state changes.
    """
    project_selected = Signal(dict)
    logout_requested = Signal()
    collapse_toggled = Signal(bool)

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

        # Live timer for total time display
        # NOTE: there is deliberately no local "live timer" here any more.
        # The sidebar previously incremented `_total_seconds` once a second on
        # its own, while the task row incremented a second counter and the
        # tracking manager kept a third. Total Time Today is now written by the
        # dashboard from TimerService.elapsed_seconds(), which is derived from
        # the durable start timestamp, so there is exactly one number.

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
                width: 3px;
                background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,0.15);
                border-radius: 1px;
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

        # SVG mark — medium-large, fixed size so it never gets squeezed
        # or stretched by layout changes (collapse/expand, resizes, etc).
        self._logo_mark = QSvgWidget(self)
        self._logo_mark.load(QByteArray(MONITRA_MARK_SVG.encode()))
        self._logo_mark.setFixedSize(LOGO_MARK_SIZE, LOGO_MARK_SIZE)

        # Wordmark — large, extra-bold. No fixed height: it sizes to its
        # own font metrics so it can never get vertically clipped, and the
        # grid row centers it against the logo automatically.
        self._wordmark = QLabel("Monitra", self)
        self._wordmark.setFont(QFont("Segoe UI", WORDMARK_FONT_SIZE, QFont.Weight.Black))
        self._wordmark.setStyleSheet(
            f"color: {SIDEBAR_TEXT}; letter-spacing: -0.5px; "
            f"font-size: {WORDMARK_FONT_SIZE}pt; font-weight: 900;"
        )

        # Collapse button
        self._collapse_btn = QPushButton("<<", self)
        self._collapse_btn.setFixedSize(28, 28)
        self._collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._collapse_btn.setToolTip("Collapse sidebar")
        self._collapse_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.07);
                border: none; border-radius: 6px;
                color: {SIDEBAR_MUTED}; font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.14);
                color: {SIDEBAR_TEXT};
            }}
        """)
        self._collapse_btn.clicked.connect(self.toggle_collapse)

        # Initial layout: horizontal row
        self._header_layout.addWidget(self._logo_mark, 0, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self._header_layout.addWidget(self._wordmark, 0, 1, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self._header_layout.addWidget(self._collapse_btn, 0, 2, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

        layout.addWidget(self._header_widget)

        # Divider 1 (permanently hidden)
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
        self._status_dot = QLabel("●", self._time_section)
        self._status_dot.setFont(QFont("Segoe UI", 16))
        self._status_dot.setStyleSheet(f"color: {SIDEBAR_MUTED}; font-size: 12px;")
        self._status_text = QLabel("Idle", self._time_section)


        # self._status_text.setFont(QFont("Segoe UI", 25, QFont.Weight.Bold))
        # self._status_text.setStyleSheet(f"color: {SIDEBAR_MUTED};")
        self._status_text.setFont(QFont("Segoe UI", STATUS_FONT_SIZE, QFont.Weight.Bold))
        self._status_text.setStyleSheet(
            f"color: {SIDEBAR_MUTED}; font-size: {STATUS_FONT_SIZE}pt; font-weight: 900;"
        )

        status_row.addWidget(self._status_dot)
        status_row.addWidget(self._status_text)
        status_row.addStretch()
        ts_layout.addLayout(status_row)

        layout.addWidget(self._time_section)

        # Divider 2 (permanently hidden)
        self._divider_2 = self._make_divider()
        self._divider_2.hide()

        # ── Project search ─────────────────────────────────────────
        self._search_section = QWidget(self)
        search_layout = QVBoxLayout(self._search_section)
        search_layout.setContentsMargins(12, 10, 12, 6)
        search_layout.setSpacing(0)

        self._search_input = QLineEdit(self._search_section)
        self._search_input.setPlaceholderText("🔍  Search projects...")
        self._search_input.setFixedHeight(34)
        self._search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self._search_input)
        layout.addWidget(self._search_section)

        # Projects label
        self._projects_header = QLabel("PROJECTS", self)
        self._projects_header.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._projects_header.setStyleSheet(f"color: {SIDEBAR_MUTED}; letter-spacing: 1.5px; padding: 4px 16px 4px 16px;")
        layout.addWidget(self._projects_header)

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
        layout.addWidget(self._scroll_area, 1)

        # Empty state label
        self._empty_label = QLabel("No projects found", self)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {SIDEBAR_MUTED}; font-size: 12px; padding: 20px;")
        self._empty_label.hide()
        layout.addWidget(self._empty_label)

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

        # Avatar circle (drawn as colored label)
        self._avatar_label = QLabel("?", self._user_card)
        self._avatar_label.setFixedSize(36, 36)
        self._avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._avatar_label.setStyleSheet(
            "background: #2563EB; color: white; border-radius: 18px;"
        )
        self._user_layout.addWidget(self._avatar_label)

        user_text_col = QVBoxLayout()
        user_text_col.setSpacing(1)
        self._user_name_label = QLabel("User", self._user_card)
        self._user_name_label.setObjectName("UserName")
        self._user_name_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        user_text_col.addWidget(self._user_name_label)

        self._user_email_label = QLabel("", self._user_card)
        self._user_email_label.setObjectName("UserEmail")
        self._user_email_label.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        user_text_col.addWidget(self._user_email_label)
        self._user_layout.addLayout(user_text_col, 1)

        self._chevron_label = QLabel("⌄", self._user_card)
        self._chevron_label.setObjectName("UserChevron")
        self._chevron_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._user_layout.addWidget(self._chevron_label)

        # Fixed user card hover using custom UserCardFrame
        # (WA_StyledBackground set in UserCardFrame.__init__ makes this
        # stylesheet render reliably in every state — no more white flash).
        # Background is explicitly set to SIDEBAR_BG (same navy as the rest
        # of the sidebar) in every non-hover state, and a top border-line
        # separates the card from the project list above it.
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

        # Trim email if too long in collapsed mode
        self._user_email_label.setVisible(not self._collapsed)
        self._user_name_label.setVisible(not self._collapsed)
        self._chevron_label.setVisible(not self._collapsed)

    def set_projects(self, projects: List[Dict[str, Any]]) -> None:
        """Rebuild the project list from real API data."""
        self._projects = projects
        self._rebuild_project_list()

    def set_total_seconds(self, total: int) -> None:
        """
        Set Total Time Today.

        The only writer is the dashboard, which supplies banked seconds plus
        the live elapsed value read from TimerService. The sidebar does not
        count time itself.
        """
        self._total_seconds = total
        self._time_display.setText(_format_seconds(self._total_seconds))

    def set_timer_active(self, active: bool) -> None:
        """Switch between Active / Idle indicator and start/stop live increment."""
        self._is_active = active
        if active:
            self._status_dot.setStyleSheet(f"color: {SUCCESS}; font-size: 12px;")
            # self._status_text.setStyleSheet(f"color: {SUCCESS};")
            self._status_text.setStyleSheet(
                f"color: {SUCCESS}; font-size: {STATUS_FONT_SIZE}pt; font-weight: 900;"
            )
            self._status_text.setText("Active")
        else:
            self._status_dot.setStyleSheet(f"color: {SIDEBAR_MUTED}; font-size: 12px;")
            # self._status_text.setStyleSheet(f"color: {SIDEBAR_MUTED};")
            self._status_text.setStyleSheet(
                f"color: {SIDEBAR_MUTED}; font-size: {STATUS_FONT_SIZE}pt; font-weight: 900;"
            )
            self._status_text.setText("Idle")

    def select_project(self, project_id: int) -> None:
        """Highlight the given project in the list (called from outside)."""
        for item in self._project_items:
            item.setChecked(item.get_project_id() == project_id)

    def toggle_collapse(self) -> None:
        """Toggle sidebar between expanded and icon-only collapsed state."""
        self._collapsed = not self._collapsed
        self._apply_collapse_state()
        self.collapse_toggled.emit(self._collapsed)

    # ── Private helpers ────────────────────────────────────────────────────────

    def _rebuild_project_list(self) -> None:
        """Clear and repopulate project items from self._projects."""
        # Remove old project items
        for item in self._project_items:
            self._projects_layout.removeWidget(item)
            item.deleteLater()
        self._project_items.clear()

        # Filter by search
        filtered = [
            p for p in self._projects
            if self._search_text.lower() in p.get("project_name", "").lower()
        ]

        if not filtered:
            self._empty_label.show()
            self._scroll_area.hide()
        else:
            self._empty_label.hide()
            self._scroll_area.show()

        for i, project in enumerate(filtered):
            color = PROJECT_COLORS[i % len(PROJECT_COLORS)]
            item = ProjectItem(project, color, self._collapsed, self._scroll_content)
            item.clicked.connect(lambda checked, p=project, c=color: self._on_project_clicked(p, c))
            # Insert before the stretch
            self._projects_layout.insertWidget(self._projects_layout.count() - 1, item)
            self._project_items.append(item)

    def _on_project_clicked(self, project: Dict[str, Any], color: str) -> None:
        """Deselect all items, check the clicked one, emit signal."""
        pid = project.get("id")
        for item in self._project_items:
            item.setChecked(item.get_project_id() == pid)
        self.project_selected.emit(project)

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text
        self._rebuild_project_list()

    def _apply_collapse_state(self) -> None:
        """Show/hide labels based on collapse state and animate width."""
        is_col = self._collapsed
        self.setFixedWidth(COLLAPSED_WIDTH if is_col else EXPANDED_WIDTH)

        # Clear layout items
        for i in reversed(range(self._header_layout.count())):
            self._header_layout.takeAt(i)

        if is_col:
            # Collapsed mode: logo on top, » button below
            self._header_layout.addWidget(self._logo_mark, 0, 0, Qt.AlignmentFlag.AlignCenter)
            self._header_layout.addWidget(self._collapse_btn, 1, 0, Qt.AlignmentFlag.AlignCenter)
            self._wordmark.hide()
            self._header_widget.setFixedHeight(HEADER_HEIGHT_COLLAPSED)
            self._divider_1.hide()
            self._divider_2.hide()
            self._time_section.hide()
            self._search_section.hide()
            self._projects_header.hide()

            # Align avatar to center in user card
            self._user_layout.setContentsMargins(0, 8, 0, 8)
            self._user_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            # Expanded mode: Logo + Wordmark + « in a single row
            self._header_layout.addWidget(self._logo_mark, 0, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self._header_layout.addWidget(self._wordmark, 0, 1, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self._header_layout.addWidget(self._collapse_btn, 0, 2, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
            self._wordmark.show()
            self._header_widget.setFixedHeight(HEADER_HEIGHT_EXPANDED)
            # Dividers are permanently hidden
            self._divider_1.hide()
            self._divider_2.hide()
            self._time_section.show()
            self._search_section.show()
            self._projects_header.show()

            # Align avatar to left in user card
            self._user_layout.setContentsMargins(12, 8, 12, 8)
            self._user_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Update visibility of text elements in user card
        self._user_name_label.setVisible(not is_col)
        self._user_email_label.setVisible(not is_col)
        self._chevron_label.setVisible(not is_col)
        
        self._collapse_btn.setText(">>" if is_col else "<<")
        self._collapse_btn.setToolTip("Expand sidebar" if is_col else "Collapse sidebar")

        # Rebuild project items to reflect collapse state
        for item in self._project_items:
            item.set_collapsed(is_col)
            item.update()

    def _show_user_menu(self) -> None:
        """Show user dropdown menu with Sign Out action."""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: #1E2D47;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 10px;
                padding: 4px;
                color: {SIDEBAR_TEXT};
            }}
            QMenu::item {{
                padding: 9px 20px;
                border-radius: 6px;
                font-size: 13px;
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

        profile_action = menu.addAction("👤  Profile")
        profile_action.setEnabled(False)
        settings_action = menu.addAction("⚙  Settings")
        settings_action.setEnabled(False)
        menu.addSeparator()
        logout_action = menu.addAction("⮐  Sign Out")

        # Show menu above the user card
        pos = self._user_card.mapToGlobal(self._user_card.rect().topLeft())
        pos.setY(pos.y() - menu.sizeHint().height() - 4)
        action = menu.exec(pos)
        if action == logout_action:
            self.logout_requested.emit()