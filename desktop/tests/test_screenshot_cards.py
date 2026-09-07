"""The Screenshots tab renders real captures, in IST, with real activity.

Three defects were reported from a running build, and all three were visible
on screen as confident, plausible, wrong information:

* the thumbnails were gradients drawn by a `SimulatedScreenshotWidget`, not
  the user's screen;
* the capture times were the backend's UTC values printed verbatim, so a
  7:34 PM capture was labelled 2:04 PM;
* every card read "0% Activity", because the endpoint it fetched carries no
  activity at all.
"""
from __future__ import annotations

import io

import pytest

from ui.activity_section import (
    ScreenshotCard, ScreenshotThumbnail, ScreenshotsTabView,
    _flatten_timeline, _ist_clock,
)

pytest.importorskip("PIL", reason="Pillow builds the test images")


def _png(color=(20, 120, 200)) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (200, 200), color).save(buffer, format="PNG")
    return buffer.getvalue()


TIMELINE = {
    "success": True,
    "window_minutes": 10,
    "windows": [
        {
            # 14:00 UTC == 19:30 IST
            "window_start": "2026-09-07T14:00:00+00:00",
            "window_end": "2026-09-07T14:10:00+00:00",
            "activity_percentage": 62,
            "activity_measured_seconds": 120,
            "screenshots": [
                {"id": 1, "captured_at": "2026-09-07T14:04:00+00:00",
                 "monitor_number": 1, "width": 1000, "height": 1000,
                 "file_size_bytes": 26114,
                 "view_url": "/time-entry-screenshots/1/view"},
            ],
            "screenshot_count": 1,
        },
        {
            "window_start": "2026-09-07T14:10:00+00:00",
            "window_end": "2026-09-07T14:20:00+00:00",
            "activity_percentage": 0,
            "activity_measured_seconds": 0,
            "screenshots": [
                {"id": 2, "captured_at": "2026-09-07T14:17:00+00:00",
                 "monitor_number": 1, "width": 1000, "height": 1000,
                 "file_size_bytes": 25070,
                 "view_url": "/time-entry-screenshots/2/view"},
            ],
            "screenshot_count": 1,
        },
    ],
}


class TestIstClock:
    def test_a_utc_capture_is_displayed_in_ist(self, qapp):
        # The reported bug exactly: 14:04 UTC is 19:34 IST, and was rendering
        # as 2:04 PM — a real screenshot wearing a time that never happened.
        assert _ist_clock("2026-09-07T14:04:00+00:00") == "7:34 PM"

    def test_the_trailing_z_form_the_backend_emits_is_understood(self, qapp):
        assert _ist_clock("2026-09-07T14:04:00Z") == "7:34 PM"

    def test_a_naive_timestamp_is_read_as_utc_not_as_local_time(self, qapp):
        # Reading a naive backend timestamp as local time is how displayed
        # times end up 5.5 hours out.
        assert _ist_clock("2026-09-07T14:04:00") == "7:34 PM"

    def test_a_missing_or_unparseable_value_renders_nothing_invented(self, qapp):
        assert _ist_clock(None) == ""
        assert _ist_clock("") == ""
        assert _ist_clock("not-a-time") == "not-a-time"[:16]


class TestFlattenTimeline:
    def test_each_screenshot_carries_its_own_windows_activity(self, qapp):
        cards = _flatten_timeline(TIMELINE)
        by_id = {c["id"]: c for c in cards}
        assert by_id[1]["activity_percent"] == 62
        assert by_id[2]["activity_percent"] == 0
        assert by_id[1]["activity_measured_seconds"] == 120

    def test_the_window_label_is_an_ist_range(self, qapp):
        cards = _flatten_timeline(TIMELINE)
        assert cards[-1]["window_label"] == "7:30 PM - 7:40 PM"

    def test_the_screen_count_comes_from_the_window_not_from_an_assumption(self, qapp):
        # What a future SCREENSHOTS_PER_WINDOW of 3 produces. Nothing here may
        # assume a window holds exactly one.
        payload = {
            "windows": [{
                "window_start": "2026-09-07T14:00:00+00:00",
                "window_end": "2026-09-07T14:10:00+00:00",
                "activity_percentage": 50, "activity_measured_seconds": 60,
                "screenshots": [
                    {"id": n, "captured_at": f"2026-09-07T14:0{n}:00+00:00",
                     "view_url": f"/time-entry-screenshots/{n}/view"}
                    for n in (1, 2, 3)
                ],
                "screenshot_count": 3,
            }]
        }
        cards = _flatten_timeline(payload)
        assert len(cards) == 3
        assert all(c["window_screenshot_count"] == 3 for c in cards)

    def test_newest_captures_come_first(self, qapp):
        cards = _flatten_timeline(TIMELINE)
        assert [c["id"] for c in cards] == [2, 1]

    def test_an_unexpected_payload_yields_no_cards_rather_than_raising(self, qapp):
        assert _flatten_timeline(None) == []
        assert _flatten_timeline([]) == []
        assert _flatten_timeline({"windows": None}) == []


class TestThumbnail:
    def test_it_shows_nothing_until_a_real_image_arrives(self, qapp):
        # The predecessor painted a convincing fake workspace here, which is
        # how fabricated pictures came to be mistaken for the user's screen.
        thumb = ScreenshotThumbnail()
        assert thumb.state == "loading"

    def test_a_real_image_is_rendered(self, qapp):
        thumb = ScreenshotThumbnail()
        thumb.set_image(_png())
        assert thumb.state == "ready"

    def test_undecodable_bytes_report_unavailable_rather_than_a_placeholder(self, qapp):
        thumb = ScreenshotThumbnail()
        thumb.set_image(b"not an image")
        assert thumb.state == "unavailable"


class TestCard:
    def _card(self, **overrides):
        data = dict(_flatten_timeline(TIMELINE)[-1])  # the 62% window
        data.update(overrides)
        return ScreenshotCard(data)

    def test_a_card_asks_for_its_image_and_shows_it(self, qapp):
        card = self._card()
        assert card.thumbnail.state == "loading"
        card.set_image(_png())
        assert card.thumbnail.state == "ready"

    def test_a_measured_window_shows_its_percentage(self, qapp):
        from PySide6.QtWidgets import QLabel

        card = self._card()
        texts = [w.text() for w in card.findChildren(QLabel)]
        assert "62% Activity" in texts
        assert "7:34 PM" in texts

    def test_an_unmeasured_window_says_so_instead_of_claiming_zero(self, qapp):
        # "0%" and "nothing was measured" are different facts. Every card in an
        # untracked hour read a confident 0% before.
        from PySide6.QtWidgets import QLabel

        card = self._card(activity_percent=0, activity_measured_seconds=0)
        texts = [w.text() for w in card.findChildren(QLabel)]
        assert "No activity data" in texts
        assert "0% Activity" not in texts


class TestTabView:
    def test_a_card_with_no_cached_image_requests_one(self, qapp):
        view = ScreenshotsTabView()
        requested = []
        view.image_requested.connect(lambda shot: requested.append(shot["id"]))
        view.set_data(_flatten_timeline(TIMELINE))
        assert sorted(requested) == [1, 2]

    def test_a_delivered_image_reaches_its_card_and_is_cached(self, qapp):
        view = ScreenshotsTabView()
        view.set_data(_flatten_timeline(TIMELINE))
        view.deliver_image(1, _png())
        assert view._cards[1].thumbnail.state == "ready"

        # A re-render repaints from memory rather than re-downloading.
        requested = []
        view.image_requested.connect(lambda shot: requested.append(shot["id"]))
        view.render_view()
        assert requested == [2]
        assert view._cards[1].thumbnail.state == "ready"

    def test_a_failed_download_leaves_the_card_in_place(self, qapp):
        # The row is real even when its image could not be fetched; dropping
        # the card would understate how much was captured.
        view = ScreenshotsTabView()
        view.set_data(_flatten_timeline(TIMELINE))
        view.deliver_image(1, None)
        assert view._cards[1].thumbnail.state == "unavailable"
        assert len(view._cards) == 2
