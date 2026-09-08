"""
Coverage for TopBar's layout: date navigator on the left (previously
centered), and an icon-only refresh control at the top-right that emits
refresh_requested() -- replacing the Task List section's old Refresh
button, which used to drive the same dashboard refresh_data() slot.
"""
from ui.topbar import TopBar


def test_date_row_is_the_first_item_in_the_layout(qapp):
    """The date navigator used to be centered via a leading addStretch();
    it must now be flush against the left edge."""
    bar = TopBar()
    layout = bar.layout()
    first_widget = layout.itemAt(0).widget()
    assert first_widget is bar.date_row


def test_refresh_button_is_icon_only_but_visibly_a_button(qapp):
    """It carries no label, but it is no longer borderless.

    It used to be a faint transparent glyph, which was affordable while a
    second "Refresh" button sat in the sidebar footer driving the same slot.
    That duplicate is gone, so the one remaining control has to be findable:
    it takes the same bordered 34px chrome as the Request button beside it.
    """
    bar = TopBar()
    assert not bar._refresh_btn.text()
    assert not bar._refresh_btn.icon().isNull()
    assert bar._refresh_btn.height() == 34

    style = bar._refresh_btn.styleSheet()
    assert "border: 1px solid" in style
    assert "background: transparent" not in style


def test_refresh_button_click_emits_refresh_requested(qapp):
    bar = TopBar()
    received = []
    bar.refresh_requested.connect(lambda: received.append(True))
    bar._refresh_btn.click()
    assert received == [True]


def test_the_sidebar_no_longer_offers_a_second_refresh(qapp):
    """One action, one control. The sidebar's footer button emitted the very
    same request as the top bar's icon -- both ran DashboardWindow's
    refresh_data() -- so the window presented one action twice."""
    from ui.sidebar import SidebarWidget

    sidebar = SidebarWidget()
    assert not hasattr(sidebar, "_refresh_btn")
    assert not hasattr(sidebar, "refresh_requested")
    # The last-sync readout it sat beside stays: it reports, it does not act.
    assert sidebar._last_sync_label is not None


def test_status_dot_has_no_adjacent_text_label(qapp):
    """The "Online"/"Offline" text label is gone -- the dot's color (and a
    tooltip, for discoverability) is now the only status indicator."""
    bar = TopBar()
    assert not hasattr(bar, "_status_text")
    bar.set_network_state("BACKEND_REACHABLE")
    assert bar._status_dot.toolTip() == "Online"


def test_status_dot_is_not_shown_in_the_top_bar(qapp):
    """The dot itself is no longer visible -- set_network_state()/
    set_latency() (wired to NetworkService's real signals in
    dashboard_window.py) still update it without erroring, but nothing
    renders in the top bar for it."""
    bar = TopBar()
    assert bar._status_dot.isHidden()
    bar.set_network_state("NO_NETWORK")
    assert bar._status_dot.isHidden()
