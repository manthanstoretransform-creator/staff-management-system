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


def test_refresh_button_is_icon_only_with_no_button_chrome(qapp):
    bar = TopBar()
    assert not bar._refresh_btn.text()
    assert not bar._refresh_btn.icon().isNull()
    style = bar._refresh_btn.styleSheet()
    assert "border: none" in style
    assert "background: transparent" in style


def test_refresh_button_click_emits_refresh_requested(qapp):
    bar = TopBar()
    received = []
    bar.refresh_requested.connect(lambda: received.append(True))
    bar._refresh_btn.click()
    assert received == [True]


def test_status_dot_has_no_adjacent_text_label(qapp):
    """The "Online"/"Offline" text label is gone -- the dot's color (and a
    tooltip, for discoverability) is now the only status indicator."""
    bar = TopBar()
    assert not hasattr(bar, "_status_text")
    bar.set_network_state("BACKEND_REACHABLE")
    assert bar._status_dot.toolTip() == "Online"
