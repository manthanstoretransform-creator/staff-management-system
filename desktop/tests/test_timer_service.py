"""
Regression tests for tracked-time correctness.

The reported symptom was that tracked time "sometimes becomes 0". These tests
pin down the property that makes that impossible: elapsed time is a pure
function of a durable start timestamp and the current clock, so nothing a
refresh, a rebuild, a reconnect or a restart can do will change it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from background_services.timer.timer_service import (
    TIMER_STATE_KEY, TimerService, TimerStatus, parse_utc,
)


class FakeTimeEntryService:
    """Records calls; never touches the network."""

    def __init__(self, entry_id=None, fail=False):
        self.entry_id = entry_id
        self.fail = fail
        self.started = []
        self.stopped = []
        #: The client-supplied stop instant, per call. The backend now records
        #: end_time from this rather than from when the request arrives.
        self.stopped_at = []

    def start_time_entry(self, project_id, task_id, started_at=None):
        self.started.append((project_id, task_id, started_at))
        if self.fail:
            raise RuntimeError("backend unavailable")
        return self.entry_id

    def stop_time_entry(self, entry_id, timeout=None, stopped_at=None):
        self.stopped.append(entry_id)
        self.stopped_at.append(stopped_at)
        if self.fail:
            raise RuntimeError("backend unavailable")
        return {"id": entry_id, "total_seconds": 0}


class FakeSync:
    def __init__(self):
        self.enqueued = []

    def enqueue(self, action_type, payload, **kwargs):
        self.enqueued.append((action_type, payload, kwargs))
        return "queued-id"


class FakeTasks:
    """Runs submitted work inline so tests stay deterministic."""

    def __init__(self):
        self.submitted = []

    def submit(self, fn, on_success=None, on_error=None, key=None, **kwargs):
        self.submitted.append(key)
        try:
            result = fn()
        except Exception as exc:  # noqa: BLE001
            if on_error:
                on_error(exc)
        else:
            if on_success:
                on_success(result)
        return None


class FakeRuntime:
    def __init__(self, cache, time_entry_service):
        self.cache = cache
        self.sync = FakeSync()
        self.tasks = FakeTasks()
        self.time_entry_service = time_entry_service
        self.queue_floor_generation = 0


@pytest.fixture
def timer(qapp, cache):
    backend = FakeTimeEntryService(entry_id=42)
    runtime = FakeRuntime(cache, backend)
    service = TimerService(runtime, backend, cache)
    runtime.timer = service
    service.backend = backend  # for assertions
    yield service
    service.stop(timeout_ms=500)


# ── Elapsed time ──────────────────────────────────────────────────────────────

def test_elapsed_is_derived_from_the_durable_timestamp(timer):
    timer.start_tracking(project_id=1, task_id=7, task_name="Task")
    assert timer.is_running()

    # Rewrite the durable origin to 90 seconds ago; elapsed must follow it
    # exactly, because it is computed rather than counted.
    origin = datetime.now(timezone.utc) - timedelta(seconds=90)
    timer._session["started_at_utc"] = origin.isoformat()
    assert timer.elapsed_seconds() == pytest.approx(90, abs=1)


def test_elapsed_survives_repeated_reads_and_is_monotonic(timer):
    timer.start_tracking(1, 7)
    first = timer.elapsed_seconds()
    for _ in range(50):
        assert timer.elapsed_seconds() >= first


def test_elapsed_is_never_negative_if_the_clock_moves_backwards(timer):
    timer.start_tracking(1, 7)
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    timer._session["started_at_utc"] = future.isoformat()
    assert timer.elapsed_seconds() == 0


def test_stopping_reports_the_derived_elapsed_not_a_counter(timer):
    captured = {}
    timer.timer_stopped.connect(lambda payload: captured.update(payload))

    timer.start_tracking(1, 7)
    origin = datetime.now(timezone.utc) - timedelta(seconds=120)
    timer._session["started_at_utc"] = origin.isoformat()
    timer.stop_tracking()

    assert captured["elapsed_seconds"] == pytest.approx(120, abs=1)
    assert not timer.is_running()


# ── Recovery ──────────────────────────────────────────────────────────────────

def test_recovery_restores_exact_elapsed_across_a_restart(qapp, cache):
    """
    A timer left running by a dead process must recover its true elapsed time.

    The audited implementation stored a per-second counter snapshot, so any
    missed write lost time. Here the start timestamp is stored once, and the
    elapsed value is recomputed from it.
    """
    backend = FakeTimeEntryService(entry_id=99)
    runtime = FakeRuntime(cache, backend)

    first = TimerService(runtime, backend, cache)
    runtime.timer = first
    first.start_tracking(project_id=1, task_id=7, task_name="Long task")
    origin = datetime.now(timezone.utc) - timedelta(minutes=45)
    first._session["started_at_utc"] = origin.isoformat()
    first._persist()
    # Simulate the process dying: no clean stop, no final write.
    first._tick_timer.stop()

    second = TimerService(runtime, backend, cache)
    runtime.timer = second
    recovered = second.recover()

    assert recovered is not None
    assert recovered["task_id"] == 7
    assert second.is_running()
    assert second.elapsed_seconds() == pytest.approx(45 * 60, abs=2)


def test_recovery_is_idempotent(qapp, cache):
    """Recovering twice must not duplicate or restart anything."""
    backend = FakeTimeEntryService(entry_id=99)
    runtime = FakeRuntime(cache, backend)
    service = TimerService(runtime, backend, cache)
    runtime.timer = service

    service.start_tracking(1, 7)
    elapsed_before = service.elapsed_seconds()
    started_at = service._session["started_at_utc"]

    assert service.recover() is None  # already running; nothing to recover
    assert service._session["started_at_utc"] == started_at
    assert service.elapsed_seconds() >= elapsed_before
    assert [(p, t) for p, t, _ in backend.started] == [(1, 7)], (
        "recovery created a second time entry"
    )


def test_recovery_with_no_persisted_state_returns_none(qapp, cache):
    backend = FakeTimeEntryService()
    runtime = FakeRuntime(cache, backend)
    service = TimerService(runtime, backend, cache)
    runtime.timer = service
    assert service.recover() is None


def test_unusable_persisted_record_is_discarded(qapp, cache):
    cache.save_app_state(TIMER_STATE_KEY, {"task_id": None, "started_at_utc": None})
    backend = FakeTimeEntryService()
    runtime = FakeRuntime(cache, backend)
    service = TimerService(runtime, backend, cache)
    runtime.timer = service
    assert service.recover() is None
    assert cache.load_app_state(TIMER_STATE_KEY) is None


# ── Offline behaviour ─────────────────────────────────────────────────────────

def test_backend_failure_does_not_stop_the_users_clock(qapp, cache):
    """Going offline must not stop tracking; the operation is queued instead."""
    backend = FakeTimeEntryService(fail=True)
    runtime = FakeRuntime(cache, backend)
    service = TimerService(runtime, backend, cache)
    runtime.timer = service

    service.start_tracking(project_id=1, task_id=7, task_name="Offline task")

    assert service.is_running(), "the timer stopped because the backend was down"
    assert service.status == TimerStatus.RUNNING
    queued = [a for a in runtime.sync.enqueued if a[0] == "start_timer"]
    assert queued, "the failed start was not queued durably"


def test_stop_while_offline_queues_the_stop(qapp, cache):
    backend = FakeTimeEntryService(entry_id=55)
    runtime = FakeRuntime(cache, backend)
    service = TimerService(runtime, backend, cache)
    runtime.timer = service

    service.start_tracking(1, 7)
    backend.fail = True
    service.stop_tracking()

    assert not service.is_running()
    assert any(a[0] == "stop_timer" for a in runtime.sync.enqueued)


# ── Remote adoption ───────────────────────────────────────────────────────────

def test_adopting_a_remote_session_anchors_to_the_server_timestamp(timer):
    server_start = datetime.now(timezone.utc) - timedelta(seconds=300)
    timer.adopt_remote_session({
        "id": 501,
        "project_id": 1,
        "task_id": 7,
        "start_time": server_start.isoformat().replace("+00:00", "Z"),
        "task": {"name": "Server task"},
    })
    assert timer.is_running()
    assert timer.entry_id == 501
    assert timer.elapsed_seconds() == pytest.approx(300, abs=2)


# ── Timestamp parsing ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected_tz", [
    ("2026-08-26T10:00:00Z", timezone.utc),
    ("2026-08-26T10:00:00+00:00", timezone.utc),
    ("2026-08-26T10:00:00", timezone.utc),  # naive is treated as UTC
])
def test_parse_utc_normalises_backend_timestamps(value, expected_tz):
    parsed = parse_utc(value)
    assert parsed is not None
    assert parsed.tzinfo == expected_tz
    assert parsed.hour == 10


def test_parse_utc_rejects_garbage():
    assert parse_utc("not a timestamp") is None
    assert parse_utc(None) is None
