"""
Monitra Design System — QSS Stylesheets and Color Constants
All visual tokens for the SMS Desktop redesign.
"""

# ─── Color Palette ────────────────────────────────────────────────────────────

# Sidebar
SIDEBAR_BG        = "#0B1526"
SIDEBAR_BG_HOVER  = "#162035"
SIDEBAR_SELECTED  = "#1E2D47"
SIDEBAR_BORDER    = "rgba(255,255,255,0.07)"
SIDEBAR_TEXT      = "#FFFFFF"
SIDEBAR_MUTED     = "#8B9DBB"

# Main content
CONTENT_BG        = "#F1F5F9"
CARD_BG           = "#FFFFFF"
TOPBAR_BG         = "#FFFFFF"
TOPBAR_BORDER     = "#E2E8F0"

# Brand
PRIMARY           = "#2563EB"
PRIMARY_HOVER     = "#1D4ED8"
PRIMARY_LIGHT     = "#EFF6FF"

# States
SUCCESS           = "#22C55E"
SUCCESS_BG        = "#F0FDF4"
WARNING           = "#F59E0B"
WARNING_BG        = "#FFFBEB"
ERROR             = "#EF4444"
ERROR_BG          = "#FEF2F2"

# Text
TEXT_PRIMARY      = "#0F172A"
TEXT_SECONDARY    = "#64748B"
TEXT_MUTED        = "#94A3B8"

# Borders
BORDER_LIGHT      = "#E2E8F0"
BORDER_MID        = "#CBD5E1"

# Project indicator colors (cycle for projects)
PROJECT_COLORS = [
    "#3B82F6", "#6366F1", "#F97316", "#22C55E",
    "#EAB308", "#8B5CF6", "#EC4899", "#14B8A6",
]

# ─── Monitra SVG Mark path data ───────────────────────────────────────────────
# Used by QPainter to draw the gradient arc + checkmark
MONITRA_MARK_SVG = """
<svg width="36" height="36" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="mg" x1="0" y1="36" x2="36" y2="0" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#9B5DE5"/>
      <stop offset="45%" stop-color="#4A7BE8"/>
      <stop offset="100%" stop-color="#41C8F4"/>
    </linearGradient>
  </defs>
  <circle cx="18" cy="18" r="14" stroke="url(#mg)" stroke-width="3.5" fill="none"
          stroke-dasharray="76 24" stroke-dashoffset="-6" stroke-linecap="round"/>
  <path d="M11 18.5l5 5L25 12" stroke="url(#mg)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""

# ─── Global Application QSS ──────────────────────────────────────────────────

APP_QSS = f"""
/* ── Application base ── */
QMainWindow {{
    background-color: {CONTENT_BG};
}}
QWidget {{
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
    color: {TEXT_PRIMARY};
}}

/* ── Scrollbars ── */
QScrollBar:vertical {{
    width: 6px;
    background: transparent;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_MID};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_MUTED};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    height: 6px;
    background: transparent;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_MID};
    border-radius: 3px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── QToolTip ── */
QToolTip {{
    background-color: {TEXT_PRIMARY};
    color: white;
    border: none;
    padding: 5px 8px;
    border-radius: 6px;
    font-size: 12px;
}}
"""

SIDEBAR_QSS = f"""
QWidget#Sidebar {{
    background-color: {SIDEBAR_BG};
    border-right: 1px solid {SIDEBAR_BORDER};
}}
"""

LOGIN_QSS = f"""
QWidget#LoginPage {{
    background-color: {CONTENT_BG};
}}
QFrame#LoginCard {{
    background-color: {CARD_BG};
    border-radius: 16px;
    border: 1px solid {BORDER_LIGHT};
}}
QLineEdit#LoginInput {{
    border: 1.5px solid {BORDER_LIGHT};
    border-radius: 8px;
    padding: 10px 14px;
    background: #F8FAFC;
    font-size: 13px;
    color: {TEXT_PRIMARY};
    selection-background-color: {PRIMARY};
}}
QLineEdit#LoginInput:focus {{
    border-color: {PRIMARY};
    background: white;
    outline: none;
}}
QPushButton#LoginBtn {{
    background-color: {PRIMARY};
    color: white;
    border-radius: 8px;
    font-weight: 600;
    font-size: 14px;
    padding: 11px 0;
    border: none;
}}
QPushButton#LoginBtn:hover {{
    background-color: {PRIMARY_HOVER};
}}
QPushButton#LoginBtn:pressed {{
    background-color: #1e40af;
}}
QPushButton#LoginBtn:disabled {{
    background-color: #93C5FD;
}}
"""

TOPBAR_QSS = f"""
QFrame#TopBar {{
    background-color: {TOPBAR_BG};
    border-bottom: 1px solid {TOPBAR_BORDER};
}}
QPushButton#HamburgerBtn {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 6px;
    color: {TEXT_SECONDARY};
    font-size: 18px;
}}
QPushButton#HamburgerBtn:hover {{
    background-color: {CONTENT_BG};
    color: {TEXT_PRIMARY};
}}
QLineEdit#GlobalSearch {{
    border: 1.5px solid {BORDER_LIGHT};
    border-radius: 8px;
    padding: 8px 14px;
    background: {CONTENT_BG};
    font-size: 13px;
    color: {TEXT_PRIMARY};
}}
QLineEdit#GlobalSearch:focus {{
    border-color: {PRIMARY};
    background: white;
}}
"""

TASK_TABLE_QSS = f"""
QFrame#TaskCard {{
    background-color: {CARD_BG};
    border-radius: 12px;
    border: 1px solid {BORDER_LIGHT};
}}
QTableWidget#TaskTable {{
    background-color: {CARD_BG};
    border: none;
    gridline-color: {BORDER_LIGHT};
    selection-background-color: {PRIMARY_LIGHT};
    outline: none;
}}
QTableWidget#TaskTable::item {{
    padding: 0px;
    border-bottom: 1px solid {BORDER_LIGHT};
}}
QTableWidget#TaskTable::item:selected {{
    background-color: {PRIMARY_LIGHT};
    color: {TEXT_PRIMARY};
}}
QHeaderView::section {{
    background-color: #F8FAFC;
    color: {TEXT_MUTED};
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 10px 16px;
    border: none;
    border-bottom: 1px solid {BORDER_LIGHT};
    border-right: none;
}}
QLineEdit#TaskSearch {{
    border: 1.5px solid {BORDER_LIGHT};
    border-radius: 10px;
    padding: 7px 14px;
    background: {CONTENT_BG};
    font-size: 12.5px;
    color: {TEXT_PRIMARY};
    selection-background-color: {PRIMARY_LIGHT};
}}
QLineEdit#TaskSearch:hover {{
    border-color: {TEXT_MUTED};
    background: white;
}}
QLineEdit#TaskSearch:focus {{
    border: 1.5px solid {PRIMARY};
    background: white;
}}
"""
