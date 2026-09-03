"""The sidebar's Feedback & Help action.

The risk this covers is not the click — it is the footer. A new fixed row
above the account card is exactly the kind of addition that made the account
card float last time, so these tests assert that the action is present and
reachable in both collapse states and that the footer keeps its order and its
height when the sidebar is toggled or hovered.
"""
import pytest

from ui.sidebar import FEEDBACK_BUTTON_SIZE, SidebarWidget

SIDEBAR_HEIGHT = 760


def _drain(qapp):
    for _ in range(6):
        qapp.processEvents()


@pytest.fixture
def sidebar(qapp):
    widget = SidebarWidget()
    widget.resize(300, SIDEBAR_HEIGHT)
    widget.show()
    _drain(qapp)
    yield widget
    widget.deleteLater()


def test_the_action_is_circular_and_named_by_its_tooltip(sidebar):
    button = sidebar._feedback_btn
    assert button.toolTip() == "Feedback & Help"
    assert button.width() == button.height() == FEEDBACK_BUTTON_SIZE
    assert f"border-radius: {FEEDBACK_BUTTON_SIZE // 2}px" in button.styleSheet()


def test_the_action_is_reachable_by_keyboard(sidebar):
    from PySide6.QtCore import Qt

    assert sidebar._feedback_btn.focusPolicy() == Qt.FocusPolicy.StrongFocus


def test_clicking_it_emits_a_request_and_opens_nothing_itself(sidebar, qapp):
    seen = []
    sidebar.feedback_requested.connect(lambda: seen.append(True))
    sidebar._feedback_btn.click()
    _drain(qapp)

    assert seen == [True]


def test_it_sits_above_the_account_card_and_below_the_project_list(sidebar, qapp):
    _drain(qapp)
    assert sidebar._feedback_row.y() < sidebar._user_card.y()
    assert sidebar._feedback_row.y() > sidebar._scroll_area.y()


def test_the_action_stays_available_when_the_sidebar_is_collapsed(sidebar, qapp):
    sidebar.toggle_collapse()
    _drain(qapp)

    assert sidebar._feedback_row.isVisible()
    assert sidebar._feedback_btn.isVisible()
    # Only the caption is dropped; the tooltip still names the action.
    assert not sidebar._feedback_label.isVisible()
    assert sidebar._feedback_btn.toolTip() == "Feedback & Help"


def test_the_button_fits_inside_the_collapsed_sidebar(sidebar, qapp):
    sidebar.toggle_collapse()
    _drain(qapp)

    assert sidebar._feedback_btn.width() <= sidebar.width()


def test_the_caption_returns_when_the_sidebar_is_expanded_again(sidebar, qapp):
    sidebar.toggle_collapse()
    _drain(qapp)
    sidebar.toggle_collapse()
    _drain(qapp)

    assert sidebar._feedback_label.isVisible()
    assert sidebar._feedback_label.text() == "Feedback & Help"


def test_the_footer_keeps_its_height_with_no_projects_and_with_many(sidebar, qapp):
    sidebar.set_projects([])
    _drain(qapp)
    empty = (sidebar._feedback_row.height(), sidebar._user_card.y(), sidebar._sync_row.y())

    sidebar.set_projects([
        {"id": i, "project_name": f"Project {i}"} for i in range(40)
    ])
    _drain(qapp)
    many = (sidebar._feedback_row.height(), sidebar._user_card.y(), sidebar._sync_row.y())

    assert empty == many


def test_hovering_does_not_resize_the_button_or_move_the_footer(sidebar, qapp):
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    before = (sidebar._feedback_btn.size(), sidebar._user_card.y())
    QApplication.sendEvent(sidebar._feedback_btn, QEvent(QEvent.Type.Enter))
    _drain(qapp)

    assert (sidebar._feedback_btn.size(), sidebar._user_card.y()) == before
