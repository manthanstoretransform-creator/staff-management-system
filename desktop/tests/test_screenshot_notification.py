"""A toast when a screenshot is captured.

The screenshot module deliberately shipped silent — a toast every ten minutes
is a lot of interruption, and the spec said so. This is the product owner
overriding that, so what these tests protect is the part that stays true
either way: the announcement is edge-triggered from the capture itself, it
names the same instant the screenshot card shows, and it cannot become a
stream.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.time_format import ist_clock


class _Recorder:
    """Stands in for BackgroundApi, capturing what would be shown."""

    def __init__(self):
        self.notifications = []

    def notify(self, message, level="info", key=None):
        self.notifications.append({"message": message, "level": level, "key": key})


def _handler():
    """The dashboard's slot, bound to a recorder rather than a real window.

    Called unbound so the test needs neither a QMainWindow nor a runtime — the
    slot's whole job is to turn one record into one notification.
    """
    from ui.dashboard_window import DashboardWindow

    api = _Recorder()
    window = SimpleNamespace(api=api)
    return lambda record: DashboardWindow._on_screenshot_captured(window, record), api


RECORD = {
    "client_screenshot_id": "abc-123",
    "time_entry_id": 2793,
    # 14:04 UTC is 19:34 IST.
    "captured_at": "2026-09-07T14:04:00+00:00",
    "window_start": "2026-09-07T14:00:00+00:00",
    "file_size_bytes": 26114,
}


class TestScreenshotNotification:
    def test_a_capture_produces_one_notification(self, qapp):
        notify, api = _handler()
        notify(RECORD)
        assert len(api.notifications) == 1

    def test_the_time_shown_is_ist_and_matches_the_card(self, qapp):
        # The toast and the screenshot card describe the same instant; if they
        # disagree the user cannot tell which one is lying.
        notify, api = _handler()
        notify(RECORD)
        assert api.notifications[0]["message"] == "Screenshot captured at 7:34 PM"
        assert ist_clock(RECORD["captured_at"]) in api.notifications[0]["message"]

    def test_it_is_informational_not_a_warning(self, qapp):
        # Nothing has gone wrong; a warning styling would suggest otherwise.
        notify, api = _handler()
        notify(RECORD)
        assert api.notifications[0]["level"] == "info"

    def test_each_capture_carries_its_own_key(self, qapp):
        # NotificationService de-duplicates by key. A shared key would let a
        # later screenshot be swallowed for resembling an earlier one.
        notify, api = _handler()
        notify(RECORD)
        notify({**RECORD, "client_screenshot_id": "def-456",
                "captured_at": "2026-09-07T14:14:00+00:00"})
        keys = [n["key"] for n in api.notifications]
        assert keys == ["screenshot:abc-123", "screenshot:def-456"]
        assert len(set(keys)) == 2

    def test_a_capture_with_no_timestamp_still_announces_itself(self, qapp):
        # Never an invented time, and never a silent capture: the user is told
        # a screenshot was taken either way.
        notify, api = _handler()
        notify({"client_screenshot_id": "x"})
        assert api.notifications[0]["message"] == "Screenshot captured"

    def test_an_unparseable_timestamp_does_not_raise(self, qapp):
        notify, api = _handler()
        notify({"client_screenshot_id": "x", "captured_at": "not-a-time"})
        assert len(api.notifications) == 1


class TestIstClockHelper:
    """One definition, used by both the card and the toast."""

    def test_utc_is_converted_to_ist(self):
        assert ist_clock("2026-09-07T14:04:00+00:00") == "7:34 PM"

    def test_the_trailing_z_form_is_understood(self):
        assert ist_clock("2026-09-07T14:04:00Z") == "7:34 PM"

    def test_a_naive_timestamp_is_read_as_utc(self):
        assert ist_clock("2026-09-07T14:04:00") == "7:34 PM"

    def test_a_datetime_is_accepted_as_well_as_a_string(self):
        from datetime import datetime, timezone

        assert ist_clock(datetime(2026, 9, 7, 14, 4, tzinfo=timezone.utc)) == "7:34 PM"

    def test_missing_values_render_as_nothing(self):
        assert ist_clock(None) == ""
        assert ist_clock("") == ""

    def test_an_unparseable_value_is_shown_as_given_not_invented(self):
        assert ist_clock("not-a-time") == "not-a-time"
