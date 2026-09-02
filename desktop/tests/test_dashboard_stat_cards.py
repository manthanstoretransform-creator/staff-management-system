"""
Coverage for the dashboard's summary-card snapshot.

The four cards must be a readout of data the window already holds -- the
day's time entries, the selected project's tasks and TimerService's session
-- and must never invent a value. In particular the running session belongs
to today alone: folding it into a past date's totals would mix two different
days, the same trap `_on_timer_tick` already avoids.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from core.time_format import ist_today


@pytest.fixture
def dashboard(qapp, runtime):
    from ui.dashboard_window import DashboardWindow

    widget = DashboardWindow(
        runtime=runtime,
        session_manager=runtime.session_manager,
        project_service=runtime.project_service,
        task_service=runtime.task_service,
        time_entry_service=runtime.time_entry_service,
        api_client=runtime.api_client,
    )
    yield widget
    widget.reset_state()
    widget.deleteLater()


def _entries():
    day = ist_today().isoformat()
    return [
        {"id": 1, "task_id": 10, "status": "stopped", "total_seconds": 3600,
         "start_time": f"{day}T09:00:00+00:00", "end_time": f"{day}T10:00:00+00:00"},
        {"id": 2, "task_id": 11, "status": "stopped", "total_seconds": 1800,
         "start_time": f"{day}T11:30:00+00:00", "end_time": f"{day}T12:00:00+00:00"},
    ]


def test_total_card_reads_the_days_banked_seconds(dashboard):
    dashboard._today_time_entries = _entries()
    dashboard._update_stat_cards()
    assert dashboard._stat_cards.total_card._value.text() == "01:30:00"


def test_work_day_spans_first_start_to_last_end(dashboard):
    """The work-day card is a span, not a sum: 09:00 -> 12:00 is three hours
    even though only 1h30m of it was tracked."""
    dashboard._today_time_entries = _entries()
    dashboard._update_stat_cards()
    assert dashboard._stat_cards.workday_card._value.text() == "03:00:00"


def test_work_day_is_empty_when_the_day_has_no_entries(dashboard):
    dashboard._today_time_entries = []
    dashboard._update_stat_cards()
    assert dashboard._stat_cards.workday_card._sub.text() == "No time logged"


def test_tasks_completed_counts_the_projects_own_statuses(dashboard):
    dashboard._current_project = {"id": 1, "project_name": "Apollo"}
    dashboard._project_tasks = [
        {"id": 10, "name": "A", "status": "completed"},
        {"id": 11, "name": "B", "status": "in_progress"},
        {"id": 12, "name": "C", "status": {"id": 3, "name": "Completed"}},
        {"id": 13, "name": "D", "status": "todo"},
    ]
    dashboard._update_stat_cards()

    assert dashboard._stat_cards.tasks_card._value.text() == "2 / 4"
    assert dashboard._stat_cards.tasks_card._progress.value() == 50


def test_tasks_card_without_a_project_says_so(dashboard):
    dashboard._current_project = None
    dashboard._project_tasks = []
    dashboard._update_stat_cards()
    assert dashboard._stat_cards.tasks_card._value.text() == "—"


def test_a_past_date_never_shows_a_running_session(dashboard, monkeypatch):
    """A historical day must show completed hours only. The live session is
    today's; adding it to another day's total would silently mix the two."""
    monkeypatch.setattr(dashboard.api, "is_timer_running", lambda: True)
    monkeypatch.setattr(dashboard.api, "timer_elapsed_seconds", lambda: 600)

    dashboard._today_time_entries = _entries()
    dashboard._current_date = ist_today() - timedelta(days=1)
    dashboard._update_stat_cards()

    assert dashboard._stat_cards.total_card._value.text() == "01:30:00"
    assert dashboard._stat_cards.total_card._sub.text() == "Not tracking"


def test_todays_running_session_is_included(dashboard, monkeypatch):
    monkeypatch.setattr(dashboard.api, "is_timer_running", lambda: True)
    monkeypatch.setattr(dashboard.api, "timer_elapsed_seconds", lambda: 600)
    monkeypatch.setattr(
        dashboard.api, "active_session",
        lambda: {"task_id": 10, "task_name": "Write the report", "project_id": 1},
    )

    dashboard._today_time_entries = _entries()
    dashboard._current_date = ist_today()
    dashboard._update_stat_cards()

    assert dashboard._stat_cards.total_card._value.text() == "01:40:00"
    assert dashboard._stat_cards.total_card._sub.text() == "Tracking now"
    assert dashboard._stat_cards.active_card._value.text() == "Write the report"


def test_signing_out_clears_the_cards(dashboard):
    dashboard._today_time_entries = _entries()
    dashboard._update_stat_cards()
    dashboard.reset_state()

    assert dashboard._stat_cards.workday_card._sub.text() == "No time logged"
    assert dashboard._stat_cards.tasks_card._value.text() == "—"
