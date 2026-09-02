"""
Coverage for the redesigned top bar: the date filter pill (chevrons around a
calendar-picker button, plus a "Today" shortcut that only exists while a past
date is shown) and the Request button that replaced the task section's
"Log Time".
"""
from datetime import timedelta

from core.time_format import ist_today
from ui.topbar import TopBar


def test_today_shortcut_is_hidden_on_today_and_shown_on_a_past_date(qapp):
    bar = TopBar()
    assert bar._today_btn.isHidden()

    bar._on_prev_day()
    assert not bar._today_btn.isHidden()
    assert bar.selected_date == ist_today() - timedelta(days=1)


def test_today_shortcut_returns_to_today_and_emits_once(qapp):
    bar = TopBar()
    bar._on_prev_day()

    seen = []
    bar.date_changed.connect(seen.append)
    bar._today_btn.click()

    assert seen == [ist_today()]
    assert bar._today_btn.isHidden()
    assert not bar.next_btn.isEnabled()


def test_selecting_the_date_already_shown_emits_nothing(qapp):
    """Picking today's date from the calendar while today is displayed must
    not trigger a reload of data that is already on screen."""
    bar = TopBar()
    seen = []
    bar.date_changed.connect(seen.append)
    bar._set_selected_date(ist_today())
    assert seen == []


def test_a_future_date_is_refused(qapp):
    bar = TopBar()
    seen = []
    bar.date_changed.connect(seen.append)
    bar._set_selected_date(ist_today() + timedelta(days=3))

    assert seen == []
    assert bar.selected_date == ist_today()


def test_date_button_label_follows_the_selection(qapp):
    bar = TopBar()
    bar._on_prev_day()
    yesterday = ist_today() - timedelta(days=1)
    assert str(yesterday.day) in bar._date_btn.text()
    assert yesterday.strftime("%B") in bar._date_btn.text()


def test_date_filter_is_still_the_first_item_in_the_layout(qapp):
    bar = TopBar()
    assert bar.layout().itemAt(0).widget() is bar.date_row


def test_request_button_click_emits_request_clicked(qapp):
    bar = TopBar()
    seen = []
    bar.request_clicked.connect(lambda: seen.append(True))
    bar._request_btn.click()
    assert seen == [True]


def test_request_button_is_labelled_request(qapp):
    bar = TopBar()
    assert bar._request_btn.text().strip() == "Request"
    assert not bar._request_btn.icon().isNull()
