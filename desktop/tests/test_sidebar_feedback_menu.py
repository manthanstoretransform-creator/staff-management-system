"""Feedback & Help in the account drop-down.

The action lives in the account menu, in the slot Settings used to hold.
The sidebar's own column is untouched by the feature, so these tests cover
the menu's contents and that the footer is exactly what it was before:
nothing added above the account card.

The menu is built by `_build_user_menu` and shown by `_show_user_menu`;
the tests use the former so they never enter `QMenu.exec`'s modal loop.
"""
import pytest

from ui.sidebar import (
    FEEDBACK_MENU_LABEL, USER_MENU_ICON_SIZE, USER_MENU_MIN_WIDTH, SidebarWidget,
)

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
    """Action labels as the user sees them.

    Qt reads `&` in an action's text as a mnemonic marker, so the label is
    stored escaped as `&&`; what is painted is a single ampersand.
    """
    return [
        a.text().replace("&&", "&") for a in built.actions() if not a.isSeparator()
    ]


def test_the_menu_offers_profile_feedback_and_sign_out(menu):
    built, _feedback, _logout = menu
    assert _labels(built) == ["Profile", "Feedback & Help", "Sign Out"]


def test_the_ampersand_is_escaped_so_it_is_not_eaten_as_a_mnemonic(menu):
    """Qt treats a lone `&` as a mnemonic marker and removes it.

    Set as "Feedback & Help", the menu painted "Feedback  Help" with the
    character simply missing, which is what was reported.
    """
    _built, feedback_action, _logout = menu

    assert FEEDBACK_MENU_LABEL == "Feedback && Help"
    assert feedback_action.text() == "Feedback && Help"
    assert feedback_action.text().replace("&&", "&") == "Feedback & Help"


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


def test_the_menu_draws_its_icons_larger_than_the_platform_default(sidebar, menu):
    """A QMenu paints action icons at PM_SmallIconSize (16px) no matter how
    large a pixmap the QIcon holds, and `QMenu::icon { width }` is ignored.
    The metric is overridden for this menu; without that the mark is tiny.
    """
    from PySide6.QtWidgets import QStyle

    built, feedback_action, _logout = menu

    assert built.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize) == (
        USER_MENU_ICON_SIZE
    )
    assert USER_MENU_ICON_SIZE > 16
    # The pixmap must actually carry that many pixels, or the style would be
    # scaling a 16px bitmap up and the mark would look soft.
    available = max(s.width() for s in feedback_action.icon().availableSizes())
    assert available >= USER_MENU_ICON_SIZE


def test_the_menus_style_object_is_kept_alive_by_the_sidebar(sidebar, menu):
    """QMenu does not take ownership of a style; a local reference would be
    collected and leave the menu pointing at freed memory."""
    assert sidebar._menu_icon_style is not None


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
