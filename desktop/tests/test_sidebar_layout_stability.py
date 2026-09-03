"""
Coverage for the sidebar's structural stability.

The sidebar is a fixed column with exactly one flexible region: the projects
area. Everything below it -- the account card and the sync footer -- must sit
at the same y whatever the project list happens to contain, and the footer
must stay flush with the bottom edge.

It did not. The project list (a QScrollArea carrying the layout's only stretch
factor) and the "No projects found" label were *siblings*, swapped with
show()/hide(). Hiding the scroll area removed the only widget claiming the
leftover vertical space, so Qt shared that space among whichever remaining
widgets had a growable size policy -- lifting the account card and opening a
gap beneath it whenever the project count reached zero.

Both states are now pages of one QStackedWidget, so they occupy identical
geometry by construction. These tests assert that with real measured
geometry rather than by reading the layout code.
"""
from __future__ import annotations

import pytest

from ui.sidebar import PROJECTS_PER_PAGE, SidebarWidget


SIDEBAR_HEIGHT = 800


def _drain(qapp):
    for _ in range(6):
        qapp.processEvents()


@pytest.fixture
def sidebar(qapp):
    widget = SidebarWidget()
    widget.resize(260, SIDEBAR_HEIGHT)
    widget.show()
    _drain(qapp)
    yield widget
    widget.deleteLater()


def _projects(n):
    return [{"id": i, "project_name": f"Project {i}"} for i in range(1, n + 1)]


def _anchors(sidebar):
    """(account y, footer y) -- the two positions that must never move."""
    return sidebar._user_card.y(), sidebar._sync_row.y()


# ── the two reported screenshots ─────────────────────────────────────────────

def test_zero_and_many_projects_place_the_account_and_footer_identically(sidebar, qapp):
    """The exact comparison from the report: PROJECTS (0) vs PROJECTS (20)."""
    sidebar.set_projects([])
    _drain(qapp)
    empty = _anchors(sidebar)

    sidebar.set_projects(_projects(20))
    _drain(qapp)
    populated = _anchors(sidebar)

    assert empty == populated


@pytest.mark.parametrize("count", [0, 1, 5, PROJECTS_PER_PAGE, PROJECTS_PER_PAGE + 1, 20, 50])
def test_the_anchors_hold_for_every_project_count(sidebar, qapp, count):
    sidebar.set_projects(_projects(count))
    _drain(qapp)
    assert _anchors(sidebar) == (
        SIDEBAR_HEIGHT - sidebar._sync_row.height() - sidebar._user_card.height(),
        SIDEBAR_HEIGHT - sidebar._sync_row.height(),
    )


def test_every_non_list_state_holds_the_same_anchors(sidebar, qapp):
    """Search-with-no-results, loading and a failed load are all messages in
    the same container, so none of them can move anything."""
    sidebar.set_projects(_projects(20))
    _drain(qapp)
    baseline = _anchors(sidebar)

    sidebar._on_search_changed("no-such-project")
    _drain(qapp)
    assert _anchors(sidebar) == baseline

    sidebar.set_projects_message("Loading projects…")
    _drain(qapp)
    assert _anchors(sidebar) == baseline

    sidebar.set_projects_message("Unable to load projects")
    _drain(qapp)
    assert _anchors(sidebar) == baseline


def test_a_long_message_does_not_grow_the_area_it_sits_in(sidebar, qapp):
    """The empty label wraps inside its page rather than pushing the column."""
    sidebar.set_projects([])
    _drain(qapp)
    baseline = _anchors(sidebar)

    sidebar.set_projects_message(
        "Unable to load projects because the server could not be reached. "
        "Check your connection and use Refresh below to try again."
    )
    _drain(qapp)
    assert _anchors(sidebar) == baseline


# ── one container, two pages ─────────────────────────────────────────────────

def test_both_states_render_inside_the_same_container(sidebar, qapp):
    sidebar.set_projects(_projects(5))
    _drain(qapp)
    listed = sidebar._projects_area.geometry()
    assert sidebar._projects_area.currentWidget() is sidebar._scroll_area

    sidebar.set_projects([])
    _drain(qapp)
    assert sidebar._projects_area.currentWidget() is sidebar._empty_page
    assert sidebar._projects_area.geometry() == listed

    # The empty state is a child of that container, not a sibling of it.
    assert sidebar._empty_label.parent() is sidebar._empty_page
    assert sidebar._projects_area.indexOf(sidebar._empty_page) >= 0


def test_the_empty_message_distinguishes_no_projects_from_no_matches(sidebar, qapp):
    sidebar.set_projects([])
    _drain(qapp)
    assert sidebar._empty_label.text() == "No projects found"

    sidebar.set_projects(_projects(3))
    sidebar._on_search_changed("zzzz")
    _drain(qapp)
    assert "search" in sidebar._empty_label.text().lower()


# ── only the projects area flexes ────────────────────────────────────────────

@pytest.mark.parametrize("height", [400, 560, 800, 1080, 1440])
@pytest.mark.parametrize("count", [0, 20])
def test_resizing_changes_only_the_projects_area(sidebar, qapp, height, count):
    sidebar.set_projects(_projects(count))
    sidebar.resize(260, height)
    _drain(qapp)

    footer_bottom = sidebar._sync_row.y() + sidebar._sync_row.height()
    assert footer_bottom == height, "the footer must stay flush with the bottom"
    assert sidebar._user_card.isVisible() and sidebar._sync_row.isVisible()
    assert sidebar._user_card.height() == 60, "the account card keeps its height"


def test_the_projects_area_absorbs_the_whole_height_change(sidebar, qapp):
    sidebar.set_projects(_projects(5))
    sidebar.resize(260, 600)
    _drain(qapp)
    short = sidebar._projects_area.height()

    sidebar.resize(260, 1000)
    _drain(qapp)
    tall = sidebar._projects_area.height()

    assert tall - short == 400


def test_the_fixed_sections_cannot_take_leftover_space(sidebar):
    """The size policies that make the above true, asserted directly."""
    from PySide6.QtWidgets import QSizePolicy

    for section in (sidebar._header_widget, sidebar._time_section,
                    sidebar._search_section, sidebar._projects_header_widget,
                    sidebar._user_card, sidebar._sync_row):
        assert section.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed

    assert (sidebar._projects_area.sizePolicy().verticalPolicy()
            == QSizePolicy.Policy.Expanding)


# ── the list scrolls; the sidebar does not ───────────────────────────────────

def test_a_long_list_scrolls_inside_the_area_rather_than_growing_it(sidebar, qapp):
    sidebar.set_projects(_projects(PROJECTS_PER_PAGE))
    _drain(qapp)
    assert sidebar._projects_area.height() <= SIDEBAR_HEIGHT
    assert sidebar._scroll_area.widgetResizable()
    # The account card stays where it is, and on screen.
    assert sidebar._user_card.y() + sidebar._user_card.height() <= SIDEBAR_HEIGHT


# ── session transitions ──────────────────────────────────────────────────────

def test_the_layout_returns_to_the_same_structure_across_a_session(sidebar, qapp):
    """launch -> loading -> loaded -> refreshed empty -> loaded again."""
    sidebar.resize(260, SIDEBAR_HEIGHT)
    _drain(qapp)
    baseline = _anchors(sidebar)

    for step in (
        lambda: sidebar.set_projects_message("Loading projects…"),
        lambda: sidebar.set_projects(_projects(12)),
        lambda: sidebar.set_projects([]),
        lambda: sidebar.set_projects(_projects(3)),
        lambda: sidebar.set_user({"name": "A Very Long User Name Indeed",
                                  "email": "an.extremely.long.email.address@example.com"}),
    ):
        step()
        _drain(qapp)
        assert _anchors(sidebar) == baseline


def test_a_long_name_and_email_do_not_change_the_account_height(sidebar, qapp):
    sidebar.set_user({"name": "Ab", "email": "a@b.co"})
    _drain(qapp)
    short = sidebar._user_card.height()

    sidebar.set_user({
        "name": "Bartholomew Featherstonehaugh-Cholmondeley",
        "email": "bartholomew.featherstonehaugh.cholmondeley@verylongdomainname.example.com",
    })
    _drain(qapp)

    assert sidebar._user_card.height() == short == 60
    # Elided, not wrapped or overflowing.
    assert sidebar._user_name_label.width() <= sidebar._user_card.width()
