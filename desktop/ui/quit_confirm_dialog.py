"""
Quit Confirmation Dialog — visually inspired by modern SaaS styles
with Monitra branding, "Remember my choice" persistence, and custom button layouts.
"""
from typing import Optional

from PySide6.QtCore import Qt, QByteArray, QSettings
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QFrame, QGraphicsDropShadowEffect, QWidget
)
from PySide6.QtSvgWidgets import QSvgWidget

from ui.styles import (
    CONTENT_BG, PRIMARY, PRIMARY_HOVER, TEXT_PRIMARY, TEXT_SECONDARY,
    TEXT_MUTED, BORDER_LIGHT, BORDER_MID, ERROR, MONITRA_MARK_SVG
)


class QuitConfirmDialog(QDialog):
    """
    Polished custom modal dialog asking the user whether they want to quit or minimize.
    Supports 'Remember my choice' using QSettings.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Quit Monitra")
        # Frameless dialog — no native black border/frame
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(440, 270)

        self.result_action: Optional[str] = None  # "minimize", "quit", or "cancel"

        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        # Transparent outer to support drop shadow
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)

        # White main dialog card
        self.card = QFrame(self)
        self.card.setObjectName("DialogCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(28, 28, 28, 24)
        card_layout.setSpacing(14)

        # Drop shadow — soft, no black frame
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 45))
        shadow.setOffset(0, 6)
        self.card.setGraphicsEffect(shadow)

        # ── Branding row (logo + wordmark) ────────────────────────
        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        brand_row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.logo_mark = QSvgWidget(self.card)
        self.logo_mark.load(QByteArray(MONITRA_MARK_SVG.encode()))
        self.logo_mark.setFixedSize(44, 44)
        brand_row.addWidget(self.logo_mark)

        wordmark = QLabel("Monitra", self.card)
        wordmark.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        wordmark.setStyleSheet(f"color: {TEXT_PRIMARY}; letter-spacing: -0.5px;")
        brand_row.addWidget(wordmark)
        brand_row.addStretch()

        card_layout.addLayout(brand_row)

        # Thin divider
        divider = QFrame(self.card)
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {BORDER_LIGHT}; border: none;")
        card_layout.addWidget(divider)

        # ── Title + subtitle ──────────────────────────────────────
        title_label = QLabel("Do you want to quit Monitra?", self.card)
        title_label.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        title_label.setStyleSheet(f"color: {TEXT_PRIMARY};")
        card_layout.addWidget(title_label)

        sub_label = QLabel("Minimizing keeps time tracking running in the background.", self.card)
        sub_label.setFont(QFont("Segoe UI", 11))
        sub_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        sub_label.setWordWrap(True)
        card_layout.addWidget(sub_label)

        # ── Checkbox ──────────────────────────────────────────────
        self.remember_cb = QCheckBox("Remember my choice", self.card)
        self.remember_cb.setFont(QFont("Segoe UI", 11))
        self.remember_cb.setStyleSheet(f"color: {TEXT_SECONDARY}; spacing: 8px;")
        card_layout.addWidget(self.remember_cb)

        # ── Buttons ───────────────────────────────────────────────
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        buttons_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel", self.card)
        self.cancel_btn.setObjectName("SecondaryBtn")
        self.cancel_btn.setFixedSize(80, 34)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.on_cancel)
        buttons_layout.addWidget(self.cancel_btn)

        self.minimize_btn = QPushButton("Minimize", self.card)
        self.minimize_btn.setObjectName("SecondaryBtn")
        self.minimize_btn.setFixedSize(90, 34)
        self.minimize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.minimize_btn.clicked.connect(self.on_minimize)
        buttons_layout.addWidget(self.minimize_btn)

        self.quit_btn = QPushButton("Quit", self.card)
        self.quit_btn.setObjectName("DestructiveBtn")
        self.quit_btn.setFixedSize(80, 34)
        self.quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quit_btn.clicked.connect(self.on_quit)
        buttons_layout.addWidget(self.quit_btn)

        card_layout.addLayout(buttons_layout)
        outer_layout.addWidget(self.card)

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QFrame#DialogCard {{
                background-color: #FFFFFF;
                border: none;
                border-radius: 14px;
            }}
            QPushButton {{
                border-radius: 7px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#SecondaryBtn {{
                background-color: #FFFFFF;
                border: 1.5px solid {BORDER_LIGHT};
                color: {TEXT_SECONDARY};
            }}
            QPushButton#SecondaryBtn:hover {{
                background-color: #F8FAFC;
                border-color: {BORDER_MID};
                color: {TEXT_PRIMARY};
            }}
            QPushButton#SecondaryBtn:pressed {{
                background-color: #F1F5F9;
            }}
            QPushButton#DestructiveBtn {{
                background-color: {ERROR};
                border: none;
                color: #FFFFFF;
            }}
            QPushButton#DestructiveBtn:hover {{
                background-color: #DC2626;
            }}
            QPushButton#DestructiveBtn:pressed {{
                background-color: #B91C1C;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1.5px solid {BORDER_MID};
                border-radius: 4px;
                background-color: #FFFFFF;
            }}
            QCheckBox::indicator:hover {{
                border-color: {PRIMARY};
            }}
            QCheckBox::indicator:checked {{
                border-color: {PRIMARY};
                background-color: {PRIMARY};
            }}
        """)

    def on_cancel(self) -> None:
        self.result_action = "cancel"
        self.reject()

    def on_minimize(self) -> None:
        self.result_action = "minimize"
        self._save_choice_if_remembered()
        self.accept()

    def on_quit(self) -> None:
        self.result_action = "quit"
        self._save_choice_if_remembered()
        self.accept()

    def _save_choice_if_remembered(self) -> None:
        if self.remember_cb.isChecked() and self.result_action:
            settings = QSettings("Monitra", "SMSDesktop")
            settings.setValue("remember_exit_choice", self.result_action)
