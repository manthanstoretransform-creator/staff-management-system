"""Feedback & Help in the account drop-down.

The action lives in the account menu, in the slot Settings used to hold.
The sidebar's own column is untouched by the feature, so these tests cover
the menu's contents and that the footer is exactly what it was before:
nothing added above the account card.

The menu is built by `_build_user_menu` and shown by `_show_user_menu`;
the tests use the former so they never enter `QMenu.exec`'s modal loop.
"""
import pytest

from ui.sidebar import USER_MENU_MIN_WIDTH, SidebarWidget

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


@pytest.fixture
def menu(sidebar):
    built, feedback_action, logout_action = sidebar._build_user_menu()
    yield built, feedback_action, logout_action
    built.deleteLater()


def _labels(built):
    return [a.text() for a in built.actions() if not a.isSeparator()]


def test_the_menu_offers_profile_feedback_and_sign_out(menu):
    built, _feedback, _logout = menu
    assert _labels(built) == ["Profile", "Feedback & Help", "Sign Out"]


def test_settings_is_gone_and_feedback_took_its_slot(menu):
    built, _feedback, _logout = menu
    labels = _labels(built)

    assert "Settings" not in labels
    assert labels.index("Feedback & Help") == 1


def test_feedback_is_enabled_unlike_the_placeholder_profile_entry(menu):
    built, feedback_action, _logout = menu
    by_label = {a.text(): a for a in built.actions() if not a.isSeparator()}

    assert feedback_action.isEnabled()
    assert not by_label["Profile"].isEnabled()


def test_the_feedback_action_carries_a_glyph_that_renders(menu):
    _built, feedback_action, _logout = menu
    image = feedback_action.icon().pixmap(32, 32).toImage()
    opaque = sum(
        1
        for x in range(image.width())
        for y in range(image.height())
        if image.pixelColor(x, y).alpha() > 10
    )

    assert opaque > 100, "the menu action's glyph did not render"


def test_the_menu_is_wide_enough_to_read_as_part_of_the_account_panel(menu):
    built, _feedback, _logout = menu

    assert built.minimumWidth() >= USER_MENU_MIN_WIDTH
    assert built.sizeHint().width() >= USER_MENU_MIN_WIDTH


def test_the_sidebar_column_carries_no_feedback_widget_of_its_own(sidebar):
    """The feature must leave the sidebar's own layout alone."""
    assert not hasattr(sidebar, "_feedback_row")
    assert not hasattr(sidebar, "_feedback_btn")
    assert not hasattr(sidebar, "_feedback_label")


def test_the_footer_is_unchanged_with_no_projects_and_with_many(sidebar, qapp):
    sidebar.set_projects([])
    _drain(qapp)
    empty = (sidebar._user_card.y(), sidebar._sync_row.y())

    sidebar.set_projects([
        {"id": i, "project_name": f"Project {i}"} for i in range(40)
    ])
    _drain(qapp)

    assert empty == (sidebar._user_card.y(), sidebar._sync_row.y())


def test_the_account_card_still_sits_between_the_projects_and_the_sync_row(sidebar, qapp):
    _drain(qapp)

    assert sidebar._user_card.y() < sidebar._sync_row.y()
    assert sidebar._user_card.y() > sidebar._scroll_area.y()


def test_the_menu_survives_the_sidebar_being_collapsed(sidebar, qapp):
    """Collapsed, the account card is an avatar -- the menu is still its menu."""
    sidebar.toggle_collapse()
    _drain(qapp)
    built, feedback_action, _logout = sidebar._build_user_menu()

    assert feedback_action.isEnabled()
    assert _labels(built) == ["Profile", "Feedback & Help", "Sign Out"]
    built.deleteLater()
