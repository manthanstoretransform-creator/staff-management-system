"""
Coverage for the redesigned login screen.

The screen carries exactly two controls -- the credentials and Sign In. In
particular the password reveal toggle must never survive a reset(), or a
cleared form could leave the next person's typing on screen.
"""
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QLineEdit

from ui.login_window import LoginWindow


@pytest.fixture
def window(qapp):
    auth = MagicMock()
    auth.login.return_value = {"id": 1, "name": "Kairav"}
    widget = LoginWindow(auth)
    yield widget
    widget.deleteLater()


# ── Password reveal ──────────────────────────────────────────────────────────

def test_password_starts_masked(window):
    assert window.password_input.echoMode() == QLineEdit.EchoMode.Password


def test_reveal_toggle_shows_and_re_hides(window):
    window.reveal_button.setChecked(True)
    assert window.password_input.echoMode() == QLineEdit.EchoMode.Normal
    window.reveal_button.setChecked(False)
    assert window.password_input.echoMode() == QLineEdit.EchoMode.Password


def test_reset_re_masks_a_revealed_password(window):
    window.password_input.setText("secret")
    window.reveal_button.setChecked(True)
    window.reset()

    assert not window.reveal_button.isChecked()
    assert window.password_input.echoMode() == QLineEdit.EchoMode.Password
    assert window.password_input.text() == ""


# ── Messages ─────────────────────────────────────────────────────────────────

def test_the_screen_carries_no_remember_or_reset_controls(window):
    """Both were removed: a "Remember me" box and a "Forgot password?" link
    that no reset flow exists behind."""
    assert not hasattr(window, "remember_checkbox")
    assert not hasattr(window, "forgot_button")


def test_login_is_called_with_just_the_credentials(window):
    window.username_input.setText("kairav")
    window.password_input.setText("secret")
    window._handle_login()
    window.auth_service.login.assert_called_once_with("kairav", "secret")


def test_empty_credentials_are_refused_without_calling_the_service(window):
    window._handle_login()
    assert "required" in window.error_label.text()
    window.auth_service.login.assert_not_called()


def test_a_failed_login_reports_the_error_and_re_enables_the_form(window):
    window.auth_service.login.side_effect = RuntimeError("Invalid credentials")
    window.username_input.setText("kairav")
    window.password_input.setText("wrong")
    window._handle_login()

    assert window.error_label.text() == "Invalid credentials"
    assert window.login_button.isEnabled()
    assert window.username_input.isEnabled()


def test_a_successful_login_emits_the_user_and_clears_the_password(window):
    seen = []
    window.login_success.connect(seen.append)
    window.username_input.setText("kairav")
    window.password_input.setText("secret")
    window._handle_login()

    assert seen == [{"id": 1, "name": "Kairav"}]
    assert window.password_input.text() == ""
