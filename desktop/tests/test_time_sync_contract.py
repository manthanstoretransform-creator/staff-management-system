"""
Coverage for the desktop half of the canonical time contract.

Two things the desktop owes the backend, both of which it used to get wrong:

  * the *instants* -- when the user actually pressed Start and Stop. Start and
    stop calls are queued durably and retried, so the request can arrive
    minutes after the event. The backend used to stamp its own clock on
    arrival, which inflated the entry by however long the action sat in the
    queue; the desktop meanwhile kept counting from its own anchor, so the two
    disagreed by exactly that delay.
  * the *day* -- which interval "today" means. The dashboard filtered on a
    naive ``00:00:00``..``23:59:59`` pair that the backend read as UTC, so it
    was asking for a UTC calendar day while labelling it the IST day.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

from core.time_format import IST, format_hms, ist_day_bounds_utc
from app.time_entries.service import TimeEntryService


UTC = timezone.utc


# ── the IST day is one definition, shared ────────────────────────────────────

def test_the_day_filter_is_the_ist_day_expressed_in_utc():
    start, end = ist_day_bounds_utc(date(2026, 9, 2))

    assert start == datetime(2026, 9, 1, 18, 30, tzinfo=UTC)
    assert end == datetime(2026, 9, 2, 18, 30, tzinfo=UTC)
    assert end - start == timedelta(days=1)
    # Both carry an offset: a naive string is what the backend read as UTC.
    assert start.tzinfo is not None and end.tzinfo is not None


def test_the_bounds_are_half_open_so_no_second_is_lost_or_double_counted():
    _, end_of_2nd = ist_day_bounds_utc(date(2026, 9, 2))
    start_of_3rd, _ = ist_day_bounds_utc(date(2026, 9, 3))
    assert end_of_2nd == start_of_3rd


def test_the_first_minutes_of_an_ist_day_fall_inside_it():
    """00:30 IST on 2 Sept is 19:00 UTC on 1 Sept. Under the old naive filter
    this landed on the previous day's screen."""
    start, end = ist_day_bounds_utc(date(2026, 9, 2))
    moment = datetime(2026, 9, 2, 0, 30, tzinfo=IST)
    assert start <= moment < end


def test_the_last_second_of_an_ist_day_falls_inside_it():
    """The old inclusive 23:59:59 bound dropped this."""
    start, end = ist_day_bounds_utc(date(2026, 9, 2))
    moment = datetime(2026, 9, 2, 23, 59, 59, 900000, tzinfo=IST)
    assert start <= moment < end


def test_the_activity_summary_uses_the_same_definition():
    """One boundary implementation, not one per feature."""
    from background_services.activity.today_summary import (
        ist_day_bounds_utc as activity_bounds,
    )

    start, end = ist_day_bounds_utc(date(2026, 9, 2))
    assert activity_bounds(date(2026, 9, 2)) == (start.isoformat(), end.isoformat())


def test_the_dashboard_asks_the_backend_for_that_exact_interval(qapp, runtime,
                                                                monkeypatch):
    from ui.dashboard_window import DashboardWindow

    captured = {}

    class Client:
        def get(self, path, params=None, headers=None, timeout=None):
            if path == "/time-entries" and params and "start_date" in params:
                captured.update(params)
            response = MagicMock()
            response.json.return_value = []
            return response

    widget = DashboardWindow(
        runtime=runtime, session_manager=runtime.session_manager,
        project_service=runtime.project_service, task_service=runtime.task_service,
        time_entry_service=runtime.time_entry_service, api_client=Client(),
    )
    try:
        calls = []
        monkeypatch.setattr(
            widget.api, "run_in_background",
            lambda fn, on_success=None, on_error=None, key=None: calls.append(fn) or object(),
        )
        widget._user_id = 54
        widget._load_today_time(date(2026, 9, 2))
        for fn in calls:
            fn()
    finally:
        widget.deleteLater()

    start, end = ist_day_bounds_utc(date(2026, 9, 2))
    assert captured["start_date"] == start.isoformat()
    assert captured["end_date"] == end.isoformat()
    # Scoped to the signed-in user: unscoped, a caller with
    # `time_entries:view_all` gets the whole organisation's entries and the
    # dashboard sums them into TOTAL TIME TODAY.
    assert captured["user_id"] == 54


# ── the instants travel with the request ─────────────────────────────────────

def _service():
    client = MagicMock()
    client.post.return_value.json.return_value = {"id": 1}
    return TimeEntryService(client), client


def test_start_sends_the_instant_the_user_pressed_start():
    service, client = _service()
    moment = "2026-09-02T05:55:53.252837+00:00"

    service.start_time_entry(2, 3, started_at=moment)

    assert client.post.call_args.kwargs["json_data"]["started_at"] == moment


def test_stop_sends_the_instant_the_user_pressed_stop():
    service, client = _service()
    moment = "2026-09-02T08:59:03.654444+00:00"

    service.stop_time_entry(7, stopped_at=moment)

    assert client.post.call_args.kwargs["json_data"]["stopped_at"] == moment


def test_the_instants_are_omitted_when_unknown_rather_than_sent_as_null():
    """An absent field lets the backend fall back to its own clock; an
    explicit null would be an assertion that the event had no time."""
    service, client = _service()
    service.start_time_entry(2, 3)
    assert "started_at" not in client.post.call_args.kwargs["json_data"]
    service.stop_time_entry(7)
    assert "stopped_at" not in client.post.call_args.kwargs["json_data"]


def test_a_queued_stop_carries_the_original_instant_not_the_retry_time(qapp, runtime):
    """The whole point of persisting it: this action may be replayed minutes
    later, and it must still record when the user actually stopped."""
    from background_services.sync.sync_service import SyncService

    service = MagicMock()
    service.stop_time_entry.return_value = {"id": 7}
    sync = runtime.sync
    original = sync._time_entry_service
    sync._time_entry_service = service
    try:
        sync._handle_stop_timer({
            "entry_id": 7, "task_id": 3,
            "stopped_at": "2026-09-02T08:59:03.654444+00:00",
            "client_op": "timer:3:2026-09-02T05:55:53+00:00",
        })
    finally:
        sync._time_entry_service = original

    assert service.stop_time_entry.call_args.kwargs["stopped_at"] == (
        "2026-09-02T08:59:03.654444+00:00"
    )


def test_a_stop_queued_offline_records_when_the_user_actually_stopped(qapp, runtime,
                                                                     monkeypatch):
    """The timer captures the instant at the moment of the click, before any
    network work, and persists it with the queued action. This is the case
    that produced the divergence: the entry is created and stopped later, but
    both timestamps are the user's, not the queue's."""
    timer = runtime.timer
    enqueued = []
    monkeypatch.setattr(
        runtime.sync, "enqueue",
        lambda action_type, payload, **kw: enqueued.append((action_type, payload)) or "id",
    )

    timer.start_tracking(project_id=1, task_id=3)
    # No backend entry id: the start never landed, so the stop must queue.
    timer._session["entry_id"] = None
    before = datetime.now(UTC)
    timer.stop_tracking()
    after = datetime.now(UTC)

    stops = [payload for action, payload in enqueued if action == "stop_timer"]
    assert stops, f"expected a queued stop, got {[a for a, _ in enqueued]}"
    recorded = datetime.fromisoformat(stops[0]["stopped_at"])
    assert before <= recorded <= after


# ── the shared formatter ─────────────────────────────────────────────────────

def test_the_desktop_formats_the_same_seconds_the_backend_reports():
    assert format_hms(4375) == "01:12:55"
    assert format_hms(0) == "00:00:00"
    assert format_hms(90061) == "25:01:01"
