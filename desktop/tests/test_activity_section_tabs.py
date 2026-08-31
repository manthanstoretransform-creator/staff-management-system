"""
Coverage for ActivitySection's merged header: the Data/Loading/Empty
testing-only state switcher is gone, and Screenshots/Apps/URLs now sit in
its old spot, on the same line as the "Activity" title.
"""
from unittest.mock import MagicMock

from ui.activity_section import ActivitySection


def _make_section() -> ActivitySection:
    return ActivitySection(api=MagicMock(), api_client=MagicMock())


def test_state_switcher_is_gone(qapp):
    section = _make_section()
    assert not hasattr(section, "_state_controls")
    assert not hasattr(section, "btn_data")
    assert not hasattr(section, "btn_loading")
    assert not hasattr(section, "btn_empty")
    assert not hasattr(section, "change_state")


def test_tabs_share_the_title_bars_header_row(qapp):
    """Screenshots/Apps/URLs must be direct items of the same QHBoxLayout
    as the "Activity" title, not a separate row below a divider."""
    section = _make_section()
    header_row = section._title.parent().parent()  # title_container -> header
    header_layout = header_row.layout()
    widgets_in_header = [
        header_layout.itemAt(i).widget()
        for i in range(header_layout.count())
        if header_layout.itemAt(i).widget() is not None
    ]
    # The tabs live inside a small container widget added directly to the
    # header row, alongside the title container.
    tabs_container = section.tab_ss.parent()
    assert tabs_container in widgets_in_header


def test_tab_switching_still_works(qapp):
    section = _make_section()
    section.switch_tab("apps")
    assert section.tab_stack.currentWidget() is section.view_apps
    section.switch_tab("urls")
    assert section.tab_stack.currentWidget() is section.view_urls
    section.switch_tab("screenshots")
    assert section.tab_stack.currentWidget() is section.view_ss
