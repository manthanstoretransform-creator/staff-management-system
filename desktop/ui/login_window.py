"""
Login window — redesigned with Monitra branding and polished card layout.
Preserves the existing AuthService integration exactly.
"""
from typing import Optional

from PySide6.QtCore import Qt, Signal, QSize
from shiboken6 import isValid
from PySide6.QtGui import QPainter, QColor, QPen, QLinearGradient, QFont, QKeySequence
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QSizePolicy, QApplication
)
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import QByteArray

from app.auth.service import AuthService
from ui.workers import LoginWorker
from ui.styles import (
    CONTENT_BG, PRIMARY, TEXT_PRIMARY, TEXT_SECONDARY,
    ERROR, BORDER_LIGHT, LOGIN_QSS, MONITRA_MARK_SVG
)


class MonitoraLogo(QWidget):
    """Renders the Monitra logo mark (SVG gradient arc + checkmark) + wordmark side by side."""

    def __init__(self, mark_size: int = 48, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.mark_size = mark_size
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # SVG mark
        self.svg_widget = QSvgWidget(self)
        self.svg_widget.load(QByteArray(MONITRA_MARK_SVG.encode()))
        self.svg_widget.setFixedSize(mark_size, mark_size)
        layout.addWidget(self.svg_widget)

        # Wordmark label
        wordmark = QLabel("Monitra", self)
        font = QFont("Segoe UI", 26, QFont.Weight.Bold)
        wordmark.setFont(font)
        wordmark.setStyleSheet(f"color: {TEXT_PRIMARY}; letter-spacing: -0.5px;")
        layout.addWidget(wordmark)
        layout.addStretch()
        self.setFixedHeight(mark_size + 4)


class LoginWindow(QWidget):
    """
    Full-page login widget with Monitra branding.
    Emits login_success(dict) on successful authentication.
    Preserves existing AuthService.login() integration.
    """
    login_success = Signal(dict)

    def __init__(self, auth_service: AuthService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.auth_service = auth_service
        self.worker: Optional[LoginWorker] = None
        self.setObjectName("LoginPage")
        self.setStyleSheet(LOGIN_QSS)
        self._init_ui()

    def _init_ui(self) -> None:
        # Outer layout centers the card
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.setContentsMargins(20, 20, 20, 20)

        # White card
        card = QFrame(self)
        card.setObjectName("LoginCard")
        card.setFixedWidth(400)
        card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(0)

        # ── Logo ──────────────────────────────────────────────────
        logo = MonitoraLogo(mark_size=48, parent=card)
        card_layout.addWidget(logo)
        card_layout.addSpacing(28)

        # ── Heading ───────────────────────────────────────────────
        heading = QLabel("Welcome back", card)
        heading.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        heading.setStyleSheet(f"color: {TEXT_PRIMARY};")
        card_layout.addWidget(heading)

        sub = QLabel("Sign in to your account to continue", card)
        sub.setFont(QFont("Segoe UI", 13))
        sub.setStyleSheet(f"color: {TEXT_SECONDARY};")
        card_layout.addWidget(sub)
        card_layout.addSpacing(28)

        # ── Username / Email ───────────────────────────────────────
        user_label = QLabel("Email or Username", card)
        user_label.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        user_label.setStyleSheet(f"color: {TEXT_PRIMARY};")
        card_layout.addWidget(user_label)
        card_layout.addSpacing(6)

        self.username_input = QLineEdit(card)
        self.username_input.setObjectName("LoginInput")
        self.username_input.setPlaceholderText("Enter your email or username")
        self.username_input.setFixedHeight(44)
        self.username_input.returnPressed.connect(self._handle_login)
        card_layout.addWidget(self.username_input)
        card_layout.addSpacing(16)

        # ── Password ───────────────────────────────────────────────
        pwd_label = QLabel("Password", card)
        pwd_label.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        pwd_label.setStyleSheet(f"color: {TEXT_PRIMARY};")
        card_layout.addWidget(pwd_label)
        card_layout.addSpacing(6)

        self.password_input = QLineEdit(card)
        self.password_input.setObjectName("LoginInput")
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFixedHeight(44)
        self.password_input.returnPressed.connect(self._handle_login)
        card_layout.addWidget(self.password_input)
        card_layout.addSpacing(8)

        # ── Error label ────────────────────────────────────────────
        self.error_label = QLabel("", card)
        self.error_label.setFont(QFont("Segoe UI", 12))
        self.error_label.setStyleSheet(f"color: {ERROR};")
        self.error_label.setWordWrap(True)
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setMinimumHeight(20)
        card_layout.addWidget(self.error_label)
        card_layout.addSpacing(12)

        # ── Login Button ───────────────────────────────────────────
        self.login_button = QPushButton("Sign In", card)
        self.login_button.setObjectName("LoginBtn")
        self.login_button.setFixedHeight(46)
        self.login_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_button.clicked.connect(self._handle_login)
        card_layout.addWidget(self.login_button)

        outer.addWidget(card)

        # Background
        self.setStyleSheet(self.styleSheet() + f"QWidget#LoginPage {{ background-color: {CONTENT_BG}; }}")

    def _handle_login(self) -> None:
        if self.worker and isValid(self.worker) and self.worker.isRunning():
            return
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not username or not password:
            self.error_label.setText("Email/username and password are required.")
            return

        self.error_label.setText("")
        self._set_loading(True)

        self.worker = LoginWorker(self.auth_service, username, password)
        self.worker.finished.connect(self._on_login_success)
        self.worker.error.connect(self._on_login_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        self.worker.start()

    def _set_loading(self, loading: bool) -> None:
        self.username_input.setEnabled(not loading)
        self.password_input.setEnabled(not loading)
        self.login_button.setEnabled(not loading)
        self.login_button.setText("Signing in..." if loading else "Sign In")

    def _on_login_success(self, user_data: dict) -> None:
        self._set_loading(False)
        self.password_input.clear()
        self.login_success.emit(user_data)

    def _on_login_error(self, error_message: str) -> None:
        self._set_loading(False)
        self.error_label.setText(error_message)

    def reset(self) -> None:
        """Clear inputs when returning to login screen."""
        self.username_input.clear()
        self.password_input.clear()
        self.error_label.setText("")
        self._set_loading(False)
        self.username_input.setFocus()

    def show_checking_session(self) -> None:
        """Show loading indicator while restoring stored session on startup."""
        self._set_loading(True)
        self.error_label.setText("Restoring session...")
