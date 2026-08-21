import logging
from typing import Optional
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QRadialGradient, QAction

logger = logging.getLogger(__name__)


def create_app_icon() -> QIcon:
    """Programmatically generate a premium Monitra circular icon with gradient background."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Gradient background
    gradient = QRadialGradient(32, 32, 30, 32, 32)
    gradient.setColorAt(0.0, QColor("#1E3A8A"))  # Deep Blue
    gradient.setColorAt(1.0, QColor("#0F172A"))  # Slate/Slate Dark
    
    painter.setBrush(gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, 60, 60)
    
    # Accent ring
    painter.setPen(QColor("#10B981"))  # Emerald Green
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(4, 4, 56, 56)
    
    # Modern sans letter "M"
    painter.setPen(QColor("#FFFFFF"))
    font = QFont("Segoe UI", 24, QFont.Weight.ExtraBold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "M")
    
    painter.end()
    return QIcon(pixmap)


class NotificationManager(QObject):
    """
    Centralized, native desktop notification manager for Monitra.
    Utilizes QSystemTrayIcon to show system-level balloon notifications on Windows/macOS/Linux.
    """
    restore_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        
        # Load and configure system tray icon
        self._icon = create_app_icon()
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(self._icon)
        self._tray.setToolTip("Monitra — Staff Management")
        
        # Connect tray activation/click
        self._tray.activated.connect(self._on_tray_activated)
        
        # Build context menu
        self._menu = QMenu()
        
        self._restore_action = QAction("Open Monitra", self)
        self._restore_action.triggered.connect(self.restore_requested.emit)
        self._menu.addAction(self._restore_action)
        
        self._menu.addSeparator()
        
        self._quit_action = QAction("Quit", self)
        self._quit_action.triggered.connect(self.quit_requested.emit)
        self._menu.addAction(self._quit_action)
        
        self._tray.setContextMenu(self._menu)
        
        # Show tray icon (required on Windows to emit notifications)
        self._tray.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.restore_requested.emit()
        
    def show_success(self, message: str, title: str = "Monitra") -> None:
        """Display a success notification using tray icon balloon."""
        self._show(title, message, QSystemTrayIcon.MessageIcon.Information)
        
    def show_info(self, message: str, title: str = "Monitra") -> None:
        """Display an informational notification using tray icon balloon."""
        self._show(title, message, QSystemTrayIcon.MessageIcon.Information)
        
    def show_warning(self, message: str, title: str = "Monitra") -> None:
        """Display a warning notification using tray icon balloon."""
        self._show(title, message, QSystemTrayIcon.MessageIcon.Warning)
        
    def show_error(self, message: str, title: str = "Monitra") -> None:
        """Display a critical error notification using tray icon balloon."""
        self._show(title, message, QSystemTrayIcon.MessageIcon.Critical)
        
    def _show(self, title: str, message: str, icon_type: QSystemTrayIcon.MessageIcon) -> None:
        """Internal helper to emit system notifications asynchronously."""
        try:
            self._tray.showMessage(title, message, icon_type, 4000)
        except Exception as e:
            logger.error(f"Failed to display system notification: {e}")
