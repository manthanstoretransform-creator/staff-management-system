"""
Regression tests for application lifecycle.

These lock in the behaviour that the instrumented reproduction proved was
broken: threads started before QApplication existed, an unbounded worker
storm, and a process that would not exit.
"""
from __future__ import annotations

import threading
import time

import pytest

from core.service import ServiceState
from core.tasks import TaskRunner


def test_runtime_starts_no_threads_until_services_start(runtime):
    """
    Constructing the runtime must not start a single background thread.

    The audited main() started QThreads before QApplication existed. The
    runtime now defers every thread to start_services(), which the window
    calls only once the event loop is running.
    """
    for service in runtime.services.services:
        assert service.state == ServiceState.STOPPED, (
            f"{service.name} was already {service.state} before start_services()"
        )


def test_services_start_and_report_running(runtime):
    runtime.start_services()
    for service in runtime.services.services:
        assert service.state in (ServiceState.RUNNING, ServiceState.DEGRADED), (
            f"{service.name} failed to start: {service.health.as_dict()}"
        )


def live_service_threads(runtime) -> list:
    """
    Names of services whose worker thread is still alive.

    This is the Qt-level truth. `threading.active_count()` cannot be used to
    detect Qt thread leaks: CPython registers a `_DummyThread` for each foreign
    thread that runs Python code and never removes it, and `_DummyThread.is_alive()`
    always returns True — so the count keeps rising even when every OS thread
    has genuinely exited.
    """
    live = []
    for service in runtime.services.services:
        thread = getattr(service, "_thread", None)
        if thread is not None and thread.isRunning():
            live.append(service.name)
    return live


def test_shutdown_stops_every_service_and_is_clean(runtime):
    """Every service must stop within its timeout; none may be left running."""
    runtime.start_services()
    time.sleep(0.3)

    assert runtime.shutdown(timeout_ms=3000) is True

    for service in runtime.services.services:
        assert service.state == ServiceState.STOPPED, (
            f"{service.name} did not stop: {service.health.as_dict()}"
        )
    assert live_service_threads(runtime) == [], "service threads outlived shutdown"


def test_shutdown_is_idempotent(runtime):
    """
    Both the window's close handler and the post-exec() safeguard call
    shutdown(); calling it twice must be harmless.
    """
    runtime.start_services()
    assert runtime.shutdown(timeout_ms=3000) is True
    assert runtime.shutdown(timeout_ms=3000) is True


def test_repeated_start_stop_cycles_do_not_leak_threads(runtime):
    """
    Ten start/stop cycles must not grow the thread count.

    Non-deterministic failures in the audited build were timing dependent, so
    a single successful cycle proves nothing.
    """
    for cycle in range(10):
        runtime.services.start_all()
        time.sleep(0.05)
        failed = runtime.services.stop_all(timeout_ms=2000)
        assert not failed, f"cycle {cycle}: services failed to stop: {failed}"
        assert live_service_threads(runtime) == [], (
            f"cycle {cycle}: threads survived stop_all"
        )

    # The bounded pool must not have grown either.
    assert runtime.tasks.active_count <= runtime.tasks.max_concurrency()


# ── TaskRunner ────────────────────────────────────────────────────────────────

def test_task_runner_is_bounded(qapp):
    """Concurrency must be capped; the audited code had no ceiling at all."""
    runner = TaskRunner(max_concurrency=2)
    try:
        assert runner.max_concurrency() == 2
        peak = 0
        lock = threading.Lock()
        running = 0

        def work():
            nonlocal running, peak
            with lock:
                running += 1
                peak = max(peak, running)
            time.sleep(0.05)
            with lock:
                running -= 1

        for _ in range(20):
            runner.submit(work)
        assert runner.shutdown(timeout_ms=5000) is True
        assert peak <= 2, f"peak concurrency {peak} exceeded the limit of 2"
    finally:
        runner.shutdown(timeout_ms=1000)


def test_task_runner_deduplicates_by_key(qapp):
    """The same request must not be in flight twice."""
    runner = TaskRunner(max_concurrency=2)
    try:
        started = threading.Event()
        release = threading.Event()

        def work():
            started.set()
            release.wait(2.0)

        first = runner.submit(work, key="same")
        assert started.wait(2.0)
        second = runner.submit(work, key="same")
        assert first is not None
        assert second is None, "a duplicate key was allowed to run concurrently"
        release.set()
    finally:
        runner.shutdown(timeout_ms=3000)


def test_task_runner_reports_errors_rather_than_swallowing(qapp):
    """Worker exceptions must surface, not vanish into a bare except."""
    runner = TaskRunner(max_concurrency=1)
    try:
        captured = []

        def boom():
            raise ValueError("expected failure")

        runner.submit(boom, on_error=captured.append)
        deadline = time.time() + 3
        while not captured and time.time() < deadline:
            qapp.processEvents()
            time.sleep(0.01)
        assert captured, "the error callback was never invoked"
        assert isinstance(captured[0], ValueError)
    finally:
        runner.shutdown(timeout_ms=2000)


def test_task_runner_drops_results_from_a_previous_session(qapp):
    """
    A response that arrives after logout must not mutate the new session.

    Scenario from the spec: user A starts a request, logs out, user B logs in,
    A's request completes.
    """
    from core.logging_setup import bump_session_generation

    runner = TaskRunner(max_concurrency=1)
    try:
        applied = []
        release = threading.Event()

        def slow_request():
            release.wait(2.0)
            return "user A's data"

        runner.submit(slow_request, on_success=applied.append)
        # The session changes while the request is in flight.
        bump_session_generation()
        release.set()

        deadline = time.time() + 3
        while time.time() < deadline:
            qapp.processEvents()
            time.sleep(0.01)
        assert applied == [], "a stale result from a previous session was applied"
    finally:
        runner.shutdown(timeout_ms=2000)
