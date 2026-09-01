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


def test_app_rows_render_from_real_summary_data(qapp):
    """Build the rows the way a successful load does.

    Nothing here ever constructed a row, so `QProgressBar` being used at
    module level without being imported went unnoticed: every Apps and URLs
    load raised NameError inside the on_success callback, and both panels
    stayed empty no matter what the backend returned. The panels looked
    like a loading/data problem; the data was fine.
    """
    section = _make_section()
    section.view_apps.set_data([
        {"name": "Visual Studio Code", "time_str": "2h 15m", "seconds": 8100,
         "percentage": 42, "color": "#3B82F6", "letter": "VS"},
        {"name": "Google Chrome", "time_str": "1h 42m", "seconds": 6120,
         "percentage": 31, "color": "#10B981", "letter": "GC"},
    ])
    section.view_apps.set_mode("data")

    assert len(section.view_apps._apps) == 2


def test_url_rows_render_from_real_summary_data(qapp):
    section = _make_section()
    section.view_urls.set_data([
        {"url": "https://chatgpt.com/c/6a96c4ec", "title": "ChatGPT - SMS",
         "domain": "chatgpt.com", "seconds": 120, "duration_seconds": 120,
         "time_str": "2m", "percentage": 100, "color": "#3B82F6", "letter": "CH"},
    ])
    section.view_urls.set_mode("data")

    assert len(section.view_urls._urls) == 1


def test_rows_render_when_a_percentage_is_missing(qapp):
    """A row must not fall over on a partial record."""
    section = _make_section()
    section.view_apps.set_data([{"name": "Notepad", "time_str": "3m", "seconds": 180}])
    section.view_apps.set_mode("data")

    assert len(section.view_apps._apps) == 1


def _rows_in_layout(view, row_type) -> list:
    """The row widgets actually attached to the view's layout.

    Reachability matters, not mere existence: a row can be constructed and
    hold the right data while its container belongs to no layout, in which
    case Qt parks it at its size hint in the top-left corner and the panel
    looks empty.
    """
    found = []
    for index in range(view.layout.count()):
        widget = view.layout.itemAt(index).widget()
        if widget is not None:
            found.extend(widget.findChildren(row_type))
    return found


def test_url_rows_are_attached_to_the_views_layout(qapp):
    from ui.activity_section import URLRowWidget

    section = _make_section()
    section.view_urls.set_data([
        {"url": "https://chatgpt.com/c/6a96c4ec", "title": "ChatGPT - SMS",
         "domain": "chatgpt.com", "seconds": 120, "duration_seconds": 120,
         "time_str": "2m", "percentage": 60, "color": "#3B82F6", "letter": "CH"},
        {"url": "https://app.hubstaff.com/dashboard", "title": "Hubstaff - Dashboard",
         "domain": "app.hubstaff.com", "seconds": 80, "duration_seconds": 80,
         "time_str": "1m", "percentage": 40, "color": "#10B981", "letter": "HU"},
    ])
    section.view_urls.set_mode("data")

    assert len(_rows_in_layout(section.view_urls, URLRowWidget)) == 2


def test_app_rows_are_attached_to_the_views_layout(qapp):
    from ui.activity_section import AppRowWidget

    section = _make_section()
    section.view_apps.set_data([
        {"name": "Visual Studio Code", "time_str": "2h", "seconds": 7200,
         "percentage": 60, "color": "#3B82F6", "letter": "VS"},
    ])
    section.view_apps.set_mode("data")

    assert len(_rows_in_layout(section.view_apps, AppRowWidget)) == 1
