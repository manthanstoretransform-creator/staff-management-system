"""
Coverage for the local cache's date-scoped readers over real SQLite.

These are the queries that keep offline activity honest. The display path reads
a *different* set from the sync consumer, and the difference is deliberate:

  * `get_pending_app_usage` — what the uploader may send now, so it filters on
    `status = 'pending'` and on the retry schedule.
  * `get_unsynced_app_usage_between` — what the server cannot yet know about,
    which is every row still present regardless of status, inside one day.

Filtering the display path the uploader's way would make a day's totals sag
while rows were in flight and jump when they came back; not filtering by date
at all is what put last week's offline segments in today's list.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from core.time_format import IST, ist_day_bounds_utc

DAY = date(2026, 9, 8)


def _at(hour: int, minute: int = 0, second: int = 0, day: date = DAY) -> str:
    """An IST wall-clock instant, stored the way the trackers store it."""
    moment = datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=IST)
    return moment.astimezone(timezone.utc).isoformat()


def _bounds(day: date = DAY):
    start, end = ist_day_bounds_utc(day)
    return start.isoformat(), end.isoformat()


# ── app usage ─────────────────────────────────────────────────────────────────

def test_only_the_selected_days_rows_come_back(cache):
    cache.save_app_usage(1, "VS Code", "main.py", 300, _at(10, 0))
    cache.save_app_usage(1, "Chrome", "Docs", 120, _at(10, 0, day=DAY - timedelta(days=1)))
    cache.save_app_usage(1, "Slack", None, 60, _at(10, 0, day=DAY + timedelta(days=1)))

    rows = cache.get_unsynced_app_usage_between(*_bounds())

    assert [r["application_name"] for r in rows] == ["VS Code"]


def test_the_day_is_an_ist_day_not_a_utc_one(cache):
    """00:30 IST is 19:00 UTC *the previous day*. Comparing against a UTC
    calendar day would push it into yesterday's totals -- the five-and-a-half
    hour shift this codebase has already paid for once."""
    cache.save_app_usage(1, "Early", None, 60, _at(0, 30))
    cache.save_app_usage(1, "Late", None, 60, _at(23, 45))

    rows = cache.get_unsynced_app_usage_between(*_bounds())

    assert {r["application_name"] for r in rows} == {"Early", "Late"}


def test_the_window_is_half_open_at_both_ends(cache):
    """Midnight belongs to the day that is starting, not to the one ending.
    An inclusive upper bound would count a row on the boundary in both days."""
    cache.save_app_usage(1, "OnStart", None, 60, _at(0, 0, 0))
    cache.save_app_usage(1, "OnEnd", None, 60, _at(0, 0, 0, day=DAY + timedelta(days=1)))

    rows = cache.get_unsynced_app_usage_between(*_bounds())

    assert [r["application_name"] for r in rows] == ["OnStart"]


def test_the_last_second_of_the_day_is_not_dropped(cache):
    cache.save_app_usage(1, "Midnight minus one", None, 1, _at(23, 59, 59))

    rows = cache.get_unsynced_app_usage_between(*_bounds())

    assert len(rows) == 1


def test_rows_in_flight_and_rows_awaiting_retry_still_count(cache):
    """A row is deleted only once the backend has acknowledged it, so anything
    still in this table is time the day's remote total is missing -- whatever
    the row's status says about the uploader's plans for it."""
    record_id = cache.save_app_usage(1, "InFlight", None, 90, _at(11, 0))
    cache.mark_app_usage_processing([record_id])
    failed_id = cache.save_app_usage(1, "Failed", None, 45, _at(11, 30))
    cache.fail_app_usage([failed_id], "boom")

    rows = cache.get_unsynced_app_usage_between(*_bounds())

    assert {r["application_name"] for r in rows} == {"InFlight", "Failed"}


def test_an_uploaded_row_is_gone_so_it_cannot_be_double_counted(cache):
    """The merge adds the backend's total to this set. Completion deletes the
    row, which is what makes the two sets disjoint."""
    record_id = cache.save_app_usage(1, "Uploaded", None, 90, _at(12, 0))
    cache.complete_app_usage([record_id])

    assert cache.get_unsynced_app_usage_between(*_bounds()) == []


# ── url usage ─────────────────────────────────────────────────────────────────

def test_url_rows_are_filtered_by_the_same_day_window(cache):
    cache.save_url_usage(
        1, "Chrome", "github.com", "https://github.com", "GitHub", 300,
        _at(9, 0), "evt-today",
    )
    cache.save_url_usage(
        1, "Chrome", "news.example", "https://news.example", "News", 300,
        _at(9, 0, day=DAY - timedelta(days=3)), "evt-old",
    )

    rows = cache.get_unsynced_url_usage_between(*_bounds())

    assert [r["domain"] for r in rows] == ["github.com"]


def test_url_rows_keep_their_client_event_id_for_idempotency(cache):
    """The display path must not disturb what the uploader de-duplicates on."""
    cache.save_url_usage(
        1, "Chrome", "github.com", "https://github.com", "GitHub", 300,
        _at(9, 0), "evt-abc",
    )

    rows = cache.get_unsynced_url_usage_between(*_bounds())

    assert rows[0]["client_event_id"] == "evt-abc"
