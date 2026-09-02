"""
Coverage for today's activity aggregation.

The card is one number derived from three disjoint sets of measurements
(uploaded, queued, still being sampled), so the two things that can go wrong
are arithmetic -- averaging percentages instead of weighting them by duration
-- and set membership: counting a window twice, or attributing it to the wrong
calendar day. Both are covered here without a Qt application or a network.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from background_services.activity.today_summary import (
    ActivityTotals, TodaySnapshot, build_today_snapshot, ist_day_bounds_utc,
    totals_from_percent,
)
from core.time_format import IST


# ── the weighted arithmetic ──────────────────────────────────────────────────

def test_nothing_measured_is_zero_not_a_division_by_zero():
    totals = ActivityTotals()
    assert totals.measured == 0
    assert not totals.has_measurement
    assert totals.percent == 0
    assert totals.percent_exact == 0.0


def test_totals_are_weighted_by_duration_not_averaged():
    """The example from the specification: 10 minutes at 90% and an hour at
    20% is 30%, not the 55% a mean of the percentages would produce."""
    totals = totals_from_percent(90, 600) + totals_from_percent(20, 3600)
    assert totals.measured == 4200
    assert totals.percent == 30


def test_the_displayed_percentage_rounds_half_up_both_ways():
    assert totals_from_percent(72.4, 100).percent == 72
    assert totals_from_percent(72.6, 100).percent == 73


def test_out_of_range_inputs_are_clamped_rather_than_trusted():
    assert totals_from_percent(140, 60).percent == 100
    assert totals_from_percent(-20, 60).percent == 0


def test_a_zero_length_window_contributes_nothing():
    """A window with no duration is not a measurement of 0% -- counting it as
    one would drag a real percentage down with unmeasured time."""
    assert totals_from_percent(90, 0) == ActivityTotals()
    combined = totals_from_percent(90, 600) + totals_from_percent(0, 0)
    assert combined.percent == 90


# ── day boundaries ───────────────────────────────────────────────────────────

def test_the_day_is_an_ist_calendar_day_not_a_utc_one():
    start_iso, end_iso = ist_day_bounds_utc(date(2026, 9, 2))
    start = datetime.fromisoformat(start_iso)
    end = datetime.fromisoformat(end_iso)

    assert start.astimezone(IST).hour == 0
    assert start.astimezone(IST).date() == date(2026, 9, 2)
    assert end - start == timedelta(days=1)
    # 00:00 IST is 18:30 UTC on the previous day. A UTC-derived bound would
    # start at 2026-09-02T00:00Z and mix five and a half hours of the wrong
    # day into the total.
    assert start == datetime(2026, 9, 1, 18, 30, tzinfo=timezone.utc)


# ── the snapshot: remote + queued, disjoint ──────────────────────────────────

class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, payload=None, error=None):
        self._payload = payload
        self._error = error
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        if self._error is not None:
            raise self._error
        return _FakeResponse(self._payload)


class _FakeCache:
    def __init__(self, weighted=0, measured=0, error=None):
        self._row = {"weighted": weighted, "measured": measured}
        self._error = error
        self.calls = []

    def get_day_activity_totals(self, start_iso, end_iso):
        self.calls.append((start_iso, end_iso))
        if self._error is not None:
            raise self._error
        return self._row


def _payload(percent, measured, tracked=0, tracking=False):
    return {
        "success": True,
        "data": {
            "date": "2026-09-02",
            "activity_percentage": round(percent),
            "activity_percentage_exact": percent,
            "measured_seconds": measured,
            "tracked_seconds": tracked,
            "is_tracking": tracking,
        },
    }


def test_the_snapshot_adds_uploaded_and_still_queued_windows():
    """The two stores hold disjoint windows -- a local row is deleted only
    after its upload succeeded -- so they are summed, and the sum is still
    weighted by duration."""
    client = _FakeClient(_payload(20.0, 3600, tracked=3600, tracking=True))
    cache = _FakeCache(weighted=90 * 600, measured=600)

    snapshot = build_today_snapshot(client, cache, date(2026, 9, 2))

    assert snapshot.remote_ok
    assert snapshot.is_tracking
    assert snapshot.tracked_seconds == 3600
    assert snapshot.totals.measured == 4200
    assert snapshot.totals.percent == 30


def test_the_snapshot_reads_the_backend_before_the_local_queue():
    """Ordering matters: a window uploaded between the two reads must be
    counted once (locally), never twice."""
    order = []
    client = _FakeClient(_payload(50.0, 60))
    cache = _FakeCache()
    original_get, original_totals = client.get, cache.get_day_activity_totals
    client.get = lambda *a, **k: (order.append("remote"), original_get(*a, **k))[1]
    cache.get_day_activity_totals = lambda *a: (order.append("local"), original_totals(*a))[1]

    build_today_snapshot(client, cache, date(2026, 9, 2))

    assert order == ["remote", "local"]


def test_an_unreachable_backend_reports_itself_instead_of_an_empty_day():
    client = _FakeClient(error=RuntimeError("connection refused"))
    cache = _FakeCache(weighted=80 * 120, measured=120)

    snapshot = build_today_snapshot(client, cache, date(2026, 9, 2))

    assert snapshot.remote_ok is False
    # The queued windows are still real measurements and are still read.
    assert snapshot.totals.measured == 120


def test_a_broken_local_read_does_not_lose_the_backend_total():
    client = _FakeClient(_payload(60.0, 600))
    cache = _FakeCache(error=RuntimeError("database is locked"))

    snapshot = build_today_snapshot(client, cache, date(2026, 9, 2))

    assert snapshot.remote_ok
    assert snapshot.totals.percent == 60


def test_a_malformed_response_is_not_treated_as_a_successful_read():
    client = _FakeClient({"success": True})
    snapshot = build_today_snapshot(client, _FakeCache(), date(2026, 9, 2))
    assert snapshot.remote_ok is False
    assert snapshot.totals.percent == 0


def test_the_local_read_is_bounded_by_the_ist_day():
    cache = _FakeCache()
    build_today_snapshot(_FakeClient(_payload(0.0, 0)), cache, date(2026, 9, 2))
    assert cache.calls == [ist_day_bounds_utc(date(2026, 9, 2))]


# ── the local queue query ────────────────────────────────────────────────────

def test_only_todays_queued_windows_are_counted(cache):
    """Yesterday's windows must not leak into today's percentage, and today's
    must be weighted by their own lengths."""
    today = date(2026, 9, 2)
    start_iso, end_iso = ist_day_bounds_utc(today)
    inside = datetime.fromisoformat(start_iso) + timedelta(hours=5)
    before = datetime.fromisoformat(start_iso) - timedelta(seconds=1)

    cache.save_activity_sample(
        time_entry_id=1, window_start=inside.isoformat(),
        window_seconds=60, active_seconds=54, activity_percent=90,
    )
    cache.save_activity_sample(
        time_entry_id=1, window_start=(inside + timedelta(minutes=1)).isoformat(),
        window_seconds=30, active_seconds=0, activity_percent=0,
    )
    cache.save_activity_sample(
        time_entry_id=2, window_start=before.isoformat(),
        window_seconds=60, active_seconds=60, activity_percent=100,
    )

    totals = cache.get_day_activity_totals(start_iso, end_iso)

    assert totals["measured"] == 90
    assert ActivityTotals(totals["weighted"], totals["measured"]).percent == 60


def test_an_uploaded_window_leaves_the_local_total(cache):
    """Completion deletes the row, which is what keeps the local and remote
    sets disjoint and stops a synced window being counted twice."""
    today = date(2026, 9, 2)
    start_iso, end_iso = ist_day_bounds_utc(today)
    inside = datetime.fromisoformat(start_iso) + timedelta(hours=3)

    record_id = cache.save_activity_sample(
        time_entry_id=1, window_start=inside.isoformat(),
        window_seconds=60, active_seconds=60, activity_percent=100,
    )
    assert cache.get_day_activity_totals(start_iso, end_iso)["measured"] == 60

    cache.complete_activity_samples([record_id])
    assert cache.get_day_activity_totals(start_iso, end_iso) == {
        "weighted": 0, "measured": 0
    }


def test_an_empty_queue_is_zero_not_an_error(cache):
    start_iso, end_iso = ist_day_bounds_utc(date(2026, 9, 2))
    assert cache.get_day_activity_totals(start_iso, end_iso) == {
        "weighted": 0, "measured": 0
    }


# ── the live window ──────────────────────────────────────────────────────────

def test_the_live_window_is_empty_while_nothing_is_tracked(runtime):
    assert runtime.activity.live_window_totals() == ActivityTotals()


def test_the_live_window_reports_what_has_been_sampled(runtime):
    service = runtime.activity
    service._tracking = True
    service._sampled = 40
    service._active = 30
    try:
        totals = service.live_window_totals()
        assert totals.measured == 40
        assert totals.percent == 75
    finally:
        service._tracking = False
        service._sampled = 0
        service._active = 0


def test_a_snapshot_defaults_to_an_honest_empty_state():
    snapshot = TodaySnapshot()
    assert snapshot.totals.percent == 0
    assert snapshot.remote_ok is False
    assert snapshot.is_tracking is False
