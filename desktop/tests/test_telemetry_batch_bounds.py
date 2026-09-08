"""
The telemetry queues must stay bounded — in request size, and on disk.

Two production defects are pinned here.

**A batch larger than the backend accepts.** The five telemetry reads used to
return everything pending, and `SyncService` put all of it in one request. The
backend caps an app-usage and a URL-usage batch at `MAX_BATCH_RECORDS` (500),
and a day tracked offline produces far more than that: app-usage segments are
flushed at least once a minute and again on every application switch. The
first batch after reconnecting was therefore rejected 422, retried *unchanged*
— so it could never succeed — until it exhausted its retry budget, at which
point every row in it was marked `failed`. Nothing reads a `failed` row again,
so an entire offline day of application and browser usage was silently lost.

**A queue with no exit but success.** Every other path out of these tables is a
`complete_*` delete. A row that never uploads had no exit at all, so a
long-lived installation accumulated them for its whole life.

The first two tests below are the ones that would have caught the data loss:
they assert the client's batch size against the backend's own constant, read
from the backend source, so the two cannot drift apart silently.
"""
from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from background_services.sync.sync_service import SyncService
from sync.local_cache import (
    TELEMETRY_FETCH_LIMIT,
    TELEMETRY_MAX_AGE_SECONDS,
    TELEMETRY_TABLES,
)


# ── The client's bound against the backend's own ─────────────────────────────


def _backend_batch_cap(module_name: str) -> int:
    """`MAX_BATCH_RECORDS` from a backend schema module, read from disk.

    Read by path rather than imported, for the same reason
    `test_validation_framework` does it: the backend is a separate application
    with its own dependencies, and the desktop suite must not need them
    installed to check that the two agree on a shared limit.
    """
    path = (
        Path(__file__).resolve().parents[2]
        / "backend" / "app" / "schemas" / f"{module_name}.py"
    )
    if not path.is_file():
        pytest.skip("backend/ is not present in this checkout")
    match = re.search(r"^MAX_BATCH_RECORDS\s*=\s*(\d+)", path.read_text(), re.MULTILINE)
    assert match, f"{module_name} no longer declares MAX_BATCH_RECORDS"
    return int(match.group(1))


@pytest.mark.parametrize("module_name", ["time_entry_app_usage", "url_usage"])
def test_client_batch_never_exceeds_what_the_backend_accepts(module_name):
    """The bound that makes the batch acceptable at all.

    A client stricter than the server is safe here; a client looser than it
    sends a request that can only ever be rejected, and retrying an oversized
    batch unchanged is a guaranteed loss rather than a recoverable failure.
    """
    assert TELEMETRY_FETCH_LIMIT <= _backend_batch_cap(module_name)


def test_a_backlog_larger_than_the_cap_is_not_sent_in_one_request(cache):
    """The regression itself, against real SQLite.

    An offline day's worth of app-usage segments — comfortably more than the
    backend's 500 — must leave the client as several acceptable requests, not
    one impossible one.
    """
    backlog = _backend_batch_cap("time_entry_app_usage") + 200
    for index in range(backlog):
        cache.save_app_usage(
            time_entry_id=101,
            application_name="Code.exe",
            window_title="editing",
            duration_seconds=60,
            recorded_at=f"2026-09-07T{index // 3600:02d}:00:00+00:00",
        )

    sync = SyncService(MagicMock(), cache, MagicMock(), MagicMock())
    service = sync._time_entry_service

    # Drain to completion, exactly as the loop would across successive ticks.
    sizes = []
    while sync._sync_app_usage():
        sizes.append(len(service.batch_sync_app_usage.call_args.args[1]["records"]))
    sizes.append(len(service.batch_sync_app_usage.call_args.args[1]["records"]))

    assert max(sizes) <= _backend_batch_cap("time_entry_app_usage")
    assert sum(sizes) == backlog, "every captured segment must still be uploaded"
    assert cache.get_pending_app_usage() == []


def test_a_full_batch_reports_a_backlog_so_the_loop_comes_back_promptly(cache):
    """A bounded batch must not mean a slow drain.

    `tick()` reads this to choose the busy cadence over the idle one, so a
    reconnection after an offline day clears in seconds rather than draining
    200 rows every two seconds.
    """
    for index in range(TELEMETRY_FETCH_LIMIT + 1):
        cache.save_activity_sample(
            time_entry_id=101,
            window_start=f"2026-09-07T00:{index % 60:02d}:00+00:00",
            window_seconds=60, active_seconds=30,
            key_events=1, mouse_events=1,
            keyboard_strokes=1, mouse_clicks=1, mouse_movements=1,
        )
    sync = SyncService(MagicMock(), cache, MagicMock(), MagicMock())

    assert sync._sync_activity() is True     # a full read: more behind it
    assert sync._sync_activity() is False    # the tail: nothing left


def test_an_empty_queue_reports_no_backlog(cache):
    sync = SyncService(MagicMock(), cache, MagicMock(), MagicMock())
    assert sync._sync_app_usage() is False
    assert sync._sync_url_usage() is False
    assert sync._sync_unwanted_activity() is False
    assert sync._sync_adjustments() is False


# ── The queue's non-success exits ────────────────────────────────────────────


def test_exhausted_telemetry_is_requeued_at_the_next_launch(cache):
    """Captured time parked as `failed` is real measured work.

    Nothing in the application reads a `failed` row, so without this a row
    that outlasted its retry budget during an outage was discarded — over a
    condition that a launch is the most likely moment to have fixed.
    """
    cache.save_app_usage(
        time_entry_id=101, application_name="Code.exe", window_title=None,
        duration_seconds=60, recorded_at="2026-09-07T09:00:00+00:00",
    )
    [record] = cache.get_pending_app_usage()
    cache.fail_app_usage([record["id"]], "boom", max_retries=0)
    assert cache.get_pending_app_usage() == []  # parked, invisible to the consumer

    assert cache.requeue_telemetry_for_new_run() == 1

    [revived] = cache.get_pending_app_usage()
    assert revived["id"] == record["id"]
    assert revived["retry_count"] == 0, "an exhausted row needs a full budget, not a spent one"


def test_requeueing_clears_an_inherited_backoff_without_spending_retries(cache):
    """A row mid-backoff is waiting out a condition the restart may have ended.

    Its retry counter is deliberately *not* reset: it has not exhausted
    anything, and zeroing it would hand a genuinely failing row an unlimited
    budget across restarts.
    """
    cache.save_adjustment(
        record_id="adj-1", time_entry_id=101, adjustment_seconds=-600,
        reason="r", source_activity_type=None, source_key_or_action=None,
        source_client_event_id=None, recorded_at="2026-09-07T09:00:00+00:00",
    )
    cache.fail_adjustments(["adj-1"])
    assert cache.get_pending_adjustments() == []  # sitting out a backoff

    cache.requeue_telemetry_for_new_run()

    [revived] = cache.get_pending_adjustments()
    assert revived["retry_count"] == 1


def test_telemetry_older_than_the_retention_window_is_swept(cache):
    """The bound that stops cache.db growing for the life of an install."""
    record_id = cache.save_url_usage(
        time_entry_id=101, browser_name="Chrome",
        domain="github.com", url="https://github.com", page_title="GitHub",
        duration_seconds=30, recorded_at="2026-09-07T09:00:00+00:00",
        client_event_id="url-1",
    )
    # Age it past the window rather than waiting a month for it.
    cache._storage.execute(
        "UPDATE pending_url_usage SET created_at = created_at - ?",
        (TELEMETRY_MAX_AGE_SECONDS + 60,),
    )

    assert cache.purge_expired_telemetry() == 1
    assert cache.get_pending_url_usage() == []


def test_the_sweep_does_not_touch_telemetry_inside_the_window(cache):
    """It is an age sweep, not a failure sweep.

    A row is removed because the backend will no longer meaningfully accept
    it, never because an upload failed — otherwise a transient outage would
    delete the time it interrupted.
    """
    record_id = cache.save_url_usage(
        time_entry_id=101, browser_name="Chrome",
        domain="github.com", url="https://github.com", page_title="GitHub",
        duration_seconds=30, recorded_at="2026-09-07T09:00:00+00:00",
        client_event_id="url-1",
    )
    cache.fail_url_usage([record_id], "boom", max_retries=0)  # failed, but recent

    assert cache.purge_expired_telemetry() == 0
    assert cache._storage.query_one(
        "SELECT id FROM pending_url_usage WHERE id = ?", (record_id,)
    ) is not None


def test_every_telemetry_table_is_covered_by_the_housekeeping(cache):
    """The two sweeps address every table, so adding a queue cannot quietly
    leave one with success as its only exit."""
    known = {
        row["name"] for row in cache._storage.query_all(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert set(TELEMETRY_TABLES) <= known
    # Both statements must be valid against every one of them.
    cache.requeue_telemetry_for_new_run()
    cache.purge_expired_telemetry()
