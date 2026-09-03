"""Feedback & Help — the dialog's contract.

Two things are worth protecting here. The first is validation: nothing leaves
the machine until a category is chosen and a real message is typed, and a
failed submission must never cost the user what they wrote. The second is that
a double-click cannot produce two feedback records — the guard is the task
runner's de-duplication key, so the test asserts on the key actually used.
"""
import pytest

from ui.feedback_dialog import (
    CATEGORY_PLACEHOLDERS, DEFAULT_PLACEHOLDER, FEEDBACK_CATEGORIES,
    PLACEHOLDER_CATEGORY, SUBMIT_KEY, FeedbackDialog,
)


class _StubApi:
    """Stands in for BackgroundApi.

    `run_in_background` records the submission instead of running it, and
    honours the same de-duplication contract as TaskRunner: a second submit
    under a key already in flight returns None and is not run.
    """

    def __init__(self):
        self.calls = []
        self.notifications = []
        self.cancelled = []
        self._in_flight = set()

    def run_in_background(self, fn, *, on_success=None, on_error=None, key=None):
        if key in self._in_flight:
            return None
        self._in_flight.add(key)
        self.calls.append({"fn": fn, "on_success": on_success,
                           "on_error": on_error, "key": key})
        return object()

    def cancel_key(self, key):
        self.cancelled.append(key)
        self._in_flight.discard(key)

    def notify(self, message, level=None, key=None):
        self.notifications.append((message, level, key))


def _drain(qapp):
    for _ in range(6):
        qapp.processEvents()


@pytest.fixture
def submissions():
    return []


@pytest.fixture
def dialog(qapp, submissions):
    def _submitter(category, message):
        submissions.append((category, message))
        return {"id": 1, "category": category, "message": message,
                "status": "new", "created_at": "2026-09-03T10:00:00Z"}

    api = _StubApi()
    widget = FeedbackDialog(api, submitter=_submitter)
    widget.show()
    _drain(qapp)
    yield widget
    widget._alive = False
    widget.deleteLater()


def _choose(dialog, wire_value):
    index = dialog.category_combo.findData(wire_value)
    assert index >= 0
    dialog.category_combo.setCurrentIndex(index)


def test_the_dropdown_offers_exactly_the_six_supported_categories(dialog):
    labels = [dialog.category_combo.itemText(i)
              for i in range(dialog.category_combo.count())]
    assert labels == [PLACEHOLDER_CATEGORY] + [label for label, _ in FEEDBACK_CATEGORIES]
    assert labels[1:] == [
        "Suggestion", "Report a Problem", "General Feedback",
        "Need Help", "Account / Login Issue", "Other",
    ]


def test_no_category_is_selected_when_the_dialog_opens(dialog):
    assert dialog.category_combo.currentData() is None
    assert dialog.message_edit.placeholderText() == DEFAULT_PLACEHOLDER


def test_the_message_placeholder_follows_the_selected_category(dialog, qapp):
    for _label, value in FEEDBACK_CATEGORIES:
        _choose(dialog, value)
        _drain(qapp)
        assert dialog.message_edit.placeholderText() == CATEGORY_PLACEHOLDERS[value]


def test_submitting_without_a_category_sends_nothing_and_says_why(dialog, submissions):
    dialog.message_edit.setPlainText("Something useful.")
    dialog._on_submit()

    assert submissions == []
    assert dialog.api.calls == []
    assert dialog.status_label.isVisible()
    assert "category" in dialog.status_label.text().lower()


def test_submitting_an_empty_message_sends_nothing_and_says_why(dialog):
    _choose(dialog, "suggestion")
    dialog._on_submit()

    assert dialog.api.calls == []
    assert "message" in dialog.status_label.text().lower()


def test_a_whitespace_only_message_is_treated_as_empty(dialog):
    _choose(dialog, "need_help")
    dialog.message_edit.setPlainText("   \n\t   ")
    dialog._on_submit()

    assert dialog.api.calls == []
    assert "message" in dialog.status_label.text().lower()


def test_an_over_long_message_is_refused_before_any_request_is_made(dialog):
    from app.feedback.service import MESSAGE_MAX_LENGTH

    _choose(dialog, "other")
    dialog.message_edit.setPlainText("x" * (MESSAGE_MAX_LENGTH + 1))
    dialog._on_submit()

    assert dialog.api.calls == []
    assert "too long" in dialog.status_label.text().lower()


def test_a_valid_submission_sends_the_trimmed_message_and_the_wire_category(dialog, submissions):
    _choose(dialog, "report_a_problem")
    dialog.message_edit.setPlainText("  The timer resets on resume.  ")
    dialog._on_submit()

    assert len(dialog.api.calls) == 1
    dialog.api.calls[0]["fn"]()
    assert submissions == [("report_a_problem", "The timer resets on resume.")]


def test_the_button_reads_submitting_and_is_disabled_while_the_request_is_in_flight(dialog):
    _choose(dialog, "suggestion")
    dialog.message_edit.setPlainText("A thought.")
    dialog._on_submit()

    assert dialog.submit_btn.text() == "Submitting..."
    assert not dialog.submit_btn.isEnabled()
    assert not dialog.cancel_btn.isEnabled()


def test_a_second_click_while_submitting_cannot_create_a_second_record(dialog):
    _choose(dialog, "suggestion")
    dialog.message_edit.setPlainText("A thought.")
    dialog._on_submit()
    dialog._on_submit()
    dialog._on_submit()

    assert len(dialog.api.calls) == 1
    assert dialog.api.calls[0]["key"] == SUBMIT_KEY


def test_a_successful_submission_notifies_and_closes(dialog, qapp):
    _choose(dialog, "general_feedback")
    dialog.message_edit.setPlainText("Nice app.")
    dialog._on_submit()
    dialog.api.calls[0]["on_success"]({"id": 1, "status": "new"})
    _drain(qapp)

    message, _level, key = dialog.api.notifications[0]
    assert "submitted successfully" in message
    assert key == "feedback-submitted"
    assert not dialog.isVisible()


def test_a_failed_submission_keeps_what_the_user_typed_and_restores_the_button(dialog, qapp):
    _choose(dialog, "account_login_issue")
    dialog.message_edit.setPlainText("I cannot sign in.")
    dialog._on_submit()
    dialog.api.calls[0]["on_error"](
        Exception("Unable to submit feedback. Please check your internet connection and try again.")
    )
    _drain(qapp)

    assert dialog.isVisible()
    assert dialog.message_edit.toPlainText() == "I cannot sign in."
    assert dialog.category_combo.currentData() == "account_login_issue"
    assert dialog.submit_btn.text() == "Submit"
    assert dialog.submit_btn.isEnabled()
    assert "internet connection" in dialog.status_label.text()


def test_cancel_sends_nothing(dialog, submissions):
    _choose(dialog, "other")
    dialog.message_edit.setPlainText("Never mind.")
    dialog._on_cancel()

    assert submissions == []
    assert dialog.api.calls == []


def test_a_late_reply_cannot_touch_a_dialog_the_user_already_closed(dialog, qapp):
    _choose(dialog, "suggestion")
    dialog.message_edit.setPlainText("A thought.")
    dialog._on_submit()
    dialog._alive = False

    # Neither callback may raise, and neither may notify.
    dialog.api.calls[0]["on_success"]({"id": 1})
    dialog.api.calls[0]["on_error"](Exception("boom"))
    _drain(qapp)

    assert dialog.api.notifications == []
