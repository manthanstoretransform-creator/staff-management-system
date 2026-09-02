"""
Coverage for the Activity list tabs' "Load more" paging.

Both list tabs used to render every row of the summary at once, which turned
a busy day into a wall of rows and pushed the task list off screen. The
button only reveals rows that are already loaded -- it never fetches, so it
cannot fail or leave a spinner behind.
"""
from ui.activity_section import PAGE_SIZE, AppsTabView, URLsTabView


def _apps(count: int):
    return [
        {"name": f"app{i}", "seconds": count - i, "percentage": 1, "time_str": "1s"}
        for i in range(count)
    ]


def _urls(count: int):
    return [
        {"title": f"page {i}", "url": f"https://example.com/{i}", "domain": "example.com",
         "seconds": 1, "percentage": 1, "time_str": "1s"}
        for i in range(count)
    ]


def _load_more_button(view):
    from PySide6.QtWidgets import QPushButton

    _flush_deletions()
    return next(
        (b for b in view.findChildren(QPushButton) if b.objectName() == "LoadMoreBtn"),
        None,
    )


def _row_count(view, row_type) -> int:
    """Rows actually on screen.

    render_view() retires the previous list with deleteLater(), which only
    takes effect once the event loop runs -- without flushing those, a
    re-render's old rows are still children and the count double-counts.
    """
    _flush_deletions()
    return len(view.findChildren(row_type))


def _flush_deletions() -> None:
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_apps_tab_shows_one_page_and_offers_the_rest(qapp):
    from ui.activity_section import AppRowWidget

    view = AppsTabView()
    view.set_data(_apps(PAGE_SIZE + 3))
    view.set_mode("data")

    assert _row_count(view, AppRowWidget) == PAGE_SIZE
    button = _load_more_button(view)
    assert button is not None
    assert "3" in button.text()


def test_load_more_reveals_the_next_page(qapp):
    from ui.activity_section import AppRowWidget

    view = AppsTabView()
    view.set_data(_apps(PAGE_SIZE + 3))
    view.set_mode("data")
    _load_more_button(view).click()

    assert _row_count(view, AppRowWidget) == PAGE_SIZE + 3
    assert _load_more_button(view) is None      # nothing left to reveal


def test_no_button_when_everything_already_fits(qapp):
    view = AppsTabView()
    view.set_data(_apps(PAGE_SIZE))
    view.set_mode("data")
    assert _load_more_button(view) is None


def test_a_refresh_does_not_collapse_an_expanded_list(qapp):
    """The Activity panel refreshes on a timer. Re-collapsing the list under
    the user every 60 seconds would make an expanded view unusable."""
    from ui.activity_section import AppRowWidget

    view = AppsTabView()
    view.set_data(_apps(PAGE_SIZE + 3))
    view.set_mode("data")
    _load_more_button(view).click()

    view.set_data(_apps(PAGE_SIZE + 3))          # the auto-refresh
    assert _row_count(view, AppRowWidget) == PAGE_SIZE + 3


def test_urls_tab_pages_the_same_way(qapp):
    from ui.activity_section import URLRowWidget

    view = URLsTabView()
    view.set_data(_urls(PAGE_SIZE + 2))
    view.set_mode("data")

    assert _row_count(view, URLRowWidget) == PAGE_SIZE
    _load_more_button(view).click()
    assert _row_count(view, URLRowWidget) == PAGE_SIZE + 2
