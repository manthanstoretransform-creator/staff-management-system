"""
UI integration tests.

The launch/quit cycle test never reaches the dashboard, because there is no
valid session in CI. These construct the real widgets against the real runtime
and drive the flows that matter, so a wiring mistake between the UI and the
services is caught rather than discovered at runtime.
"""
from __future__ import annotations

import pytest

from background_services.public_api import BackgroundApi


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


PROJECT = {"id": 1, "project_name": "Apollo"}
TASKS = [
    {"id": 10, "name": "Write the report", "time_tracked_seconds": 0},
    {"id": 11, "name": "Review the draft", "time_tracked_seconds": 0},
]


def test_dashboard_constructs_and_wires_to_services(dashboard, runtime):
    """Construction must not raise, and must not start any work by itself."""
    assert isinstance(dashboard.api, BackgroundApi)
    assert dashboard._task_section is not None
    assert dashboard._activity_section is not None
    # Nothing should be scheduled before login.
    assert not dashboard._refresh_timer.isActive()
    assert not dashboard._activity_section._enabled


def test_login_renders_cached_data_without_waiting_on_the_network(dashboard, runtime):
    """
    Cache-first: the shell must be populated from local data immediately.

    The backend is unreachable in tests, so anything that required a response
    to render would leave the view empty.
    """
    runtime.cache.cache_projects([PROJECT])
    dashboard.on_login({"id": 1, "role_name": "member"})

    assert dashboard._projects == [PROJECT]
    assert dashboard._refresh_timer.isActive()
    assert dashboard._activity_section._enabled


def test_selecting_a_project_renders_cached_tasks(dashboard, runtime):
    runtime.cache.cache_projects([PROJECT])
    runtime.cache.cache_tasks(1, TASKS)
    dashboard.on_login({"id": 1, "role_name": "member"})

    dashboard._on_project_selected(PROJECT)

    assert dashboard._current_project == PROJECT
    assert len(dashboard._task_section._task_rows) == 2
    assert dashboard._task_section._has_loaded_tasks is True


def test_a_late_response_for_a_project_the_user_left_is_discarded(dashboard, runtime):
    """A slow reply must never overwrite a newer selection."""
    runtime.cache.cache_projects([PROJECT])
    dashboard.on_login({"id": 1, "role_name": "member"})
    dashboard._on_project_selected(PROJECT)

    other = {"id": 2, "project_name": "Borealis"}
    dashboard._current_project = other

    dashboard._on_tasks_loaded(1, TASKS)  # response for the *old* project

    assert dashboard._current_project == other, "a stale response changed the selection"
    assert runtime.cache.get_cached_tasks(1) is None, (
        "a response for an abandoned project was written to the cache"
    )


def test_timer_start_and_stop_drive_the_rows_through_the_service(dashboard, runtime):
    """
    The row must reflect the service, and must not count time itself.

    The backend is unreachable, so this also proves the timer runs offline.
    """
    runtime.cache.cache_projects([PROJECT])
    runtime.cache.cache_tasks(1, TASKS)
    dashboard.on_login({"id": 1, "role_name": "member"})
    dashboard._on_project_selected(PROJECT)

    row = dashboard._task_section._task_rows[0]
    assert row._is_running is False

    dashboard._task_section._handle_start_request(row)

    assert runtime.timer.is_running()
    assert runtime.timer.task_id == 10
    assert row._is_running is True, "the row did not follow the timer service"
    assert dashboard._task_section._running_task_id == 10

    dashboard._task_section._handle_stop_request(row)

    assert not runtime.timer.is_running()
    assert row._is_running is False
    assert dashboard._task_section._running_task_id is None


def test_starting_a_second_task_switches_rather_than_stacking(dashboard, runtime):
    """The single-active-timer rule must hold through the service."""
    runtime.cache.cache_projects([PROJECT])
    runtime.cache.cache_tasks(1, TASKS)
    dashboard.on_login({"id": 1, "role_name": "member"})
    dashboard._on_project_selected(PROJECT)

    first, second = dashboard._task_section._task_rows
    dashboard._task_section._handle_start_request(first)
    dashboard._task_section._handle_start_request(second)

    assert runtime.timer.task_id == 11
    assert first._is_running is False, "two rows were running at once"
    assert second._is_running is True


def test_rebuilding_rows_does_not_lose_the_running_timer(dashboard, runtime):
    """
    A refresh must not reset tracked time.

    Rows are destroyed and rebuilt on every task refresh. Because elapsed time
    lives in the service, the rebuilt row shows the same value.
    """
    runtime.cache.cache_projects([PROJECT])
    runtime.cache.cache_tasks(1, TASKS)
    dashboard.on_login({"id": 1, "role_name": "member"})
    dashboard._on_project_selected(PROJECT)

    row = dashboard._task_section._task_rows[0]
    dashboard._task_section._handle_start_request(row)
    elapsed_before = runtime.timer.elapsed_seconds()

    dashboard._task_section._rebuild_rows()  # full refresh

    assert runtime.timer.is_running(), "a UI refresh stopped the timer"
    assert runtime.timer.elapsed_seconds() >= elapsed_before
    rebuilt = next(
        r for r in dashboard._task_section._task_rows if r.task.get("id") == 10
    )
    assert rebuilt._is_running is True, "the rebuilt row lost the running state"


def test_logout_clears_session_state_and_stops_scheduling(dashboard, runtime):
    runtime.cache.cache_projects([PROJECT])
    dashboard.on_login({"id": 1, "role_name": "member"})
    assert dashboard._refresh_timer.isActive()

    dashboard.reset_state()

    assert dashboard._projects == []
    assert dashboard._current_project is None
    assert not dashboard._refresh_timer.isActive()
    assert not dashboard._activity_section._enabled


def test_refresh_is_skipped_while_the_backend_is_known_unusable(dashboard, runtime):
    """Refreshing into a known outage produces only retry noise."""
    from background_services.network import NetworkState

    runtime.cache.cache_projects([PROJECT])
    dashboard.on_login({"id": 1, "role_name": "member"})

    runtime.network._state = NetworkState.NO_NETWORK
    before = runtime.tasks.in_flight
    dashboard.refresh_data()
    assert runtime.tasks.in_flight <= before


def test_first_network_observation_is_not_announced_as_a_recovery(dashboard, runtime):
    """
    Telling the user they are "back online" before they were seen offline was
    part of the reported notification noise.
    """
    from background_services.network import NetworkState

    shown = []
    runtime.notifications.notify = lambda *a, **kw: shown.append(a)

    dashboard._on_network_state_changed(NetworkState.BACKEND_REACHABLE)
    assert shown == [], "the first observation produced a 'back online' notice"

    dashboard._on_network_state_changed(NetworkState.NO_NETWORK)
    dashboard._on_network_state_changed(NetworkState.BACKEND_REACHABLE)
    assert any("Back online" in str(a) for a in shown), "a real recovery was not announced"
