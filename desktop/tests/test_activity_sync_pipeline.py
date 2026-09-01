"""
The sync half of the activity/unwanted-activity pipeline:

- LocalCache round-trips for the new activity count columns and the two
  new offline queues (real SQLite via the storage fixture, including the
  additive column migration on activity_samples).
- SyncService drains: batch payload shapes match the backend schemas
  exactly, completion deletes, failure retries with backoff instead of
  dropping -- and a deduction is only ever uploaded with its idempotency
  key.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from background_services.sync.sync_service import SyncService


# ── LocalCache round-trips (real SQLite) ─────────────────────────────────────


def test_activity_sample_round_trip_includes_counts(cache):
    cache.save_activity_sample(
        time_entry_id=101, window_start="2026-08-31T12:00:00+00:00",
        window_seconds=60, active_seconds=45, key_events=30, mouse_events=20,
        keyboard_strokes=120, mouse_clicks=35, mouse_movements=900,
    )
    [sample] = cache.get_pending_activity_samples()
    assert sample["keyboard_strokes"] == 120
    assert sample["mouse_clicks"] == 35
    assert sample["mouse_movements"] == 900
    assert sample["activity_percent"] == 75  # 45/60, derived not fabricated


def test_unwanted_activity_queue_round_trip(cache):
    cache.save_unwanted_activity(
        record_id="evt-1", time_entry_id=101, activity_type="repeated_key",
        key_or_action="ctrl", occurrence_count=15, alerted=True, alert_count=2,
        recorded_at="2026-08-31T12:00:00+00:00",
    )
    [event] = cache.get_pending_unwanted_activity()
    assert event["id"] == "evt-1"
    assert event["key_or_action"] == "ctrl"
    assert event["alerted"] == 1
    assert event["alert_count"] == 2

    cache.complete_unwanted_activity(["evt-1"])
    assert cache.get_pending_unwanted_activity() == []


def test_adjustment_queue_round_trip_and_duplicate_insert_ignored(cache):
    for _ in range(2):  # the id is the idempotency key: second insert ignored
        cache.save_adjustment(
            record_id="adj-1", time_entry_id=101, adjustment_seconds=-600,
            reason="3 occurrences", source_activity_type="repeated_key",
            source_key_or_action="ctrl", source_client_event_id="evt-1",
            recorded_at="2026-08-31T12:00:00+00:00",
        )
    pending = cache.get_pending_adjustments()
    assert len(pending) == 1
    assert pending[0]["adjustment_seconds"] == -600
    assert pending[0]["source_client_event_id"] == "evt-1"


def test_failed_uploads_back_off_instead_of_dropping(cache):
    cache.save_adjustment(
        record_id="adj-1", time_entry_id=101, adjustment_seconds=-600,
        reason="r", source_activity_type=None, source_key_or_action=None,
        source_client_event_id=None, recorded_at="2026-08-31T12:00:00+00:00",
    )
    cache.fail_adjustments(["adj-1"])
    # Backoff: not pending right now, but not deleted or failed either.
    assert cache.get_pending_adjustments() == []
    row = cache._storage.query_one(
        "SELECT status, retry_count, next_retry_at FROM pending_adjustments WHERE id = ?",
        ("adj-1",),
    )
    assert row["status"] == "pending"
    assert row["retry_count"] == 1
    assert row["next_retry_at"] > 0


# ── SyncService drains (mocked cache/service) ────────────────────────────────


def _sync_with_mocks():
    cache = MagicMock()
    time_entry_service = MagicMock()
    runtime = MagicMock()
    runtime.queue_floor_generation = 0
    sync = SyncService(runtime, cache, time_entry_service, MagicMock())
    return sync, cache, time_entry_service


def test_activity_batch_payload_matches_the_backend_schema():
    sync, cache, service = _sync_with_mocks()
    cache.get_pending_activity_samples.return_value = [{
        "id": "sample-1", "time_entry_id": 101,
        "window_start": "2026-08-31T12:00:00+00:00", "window_seconds": 60,
        "active_seconds": 45, "key_events": 30, "mouse_events": 20,
        "keyboard_strokes": 120, "mouse_clicks": 35, "mouse_movements": 900,
        "activity_percent": 75, "retry_count": 0,
    }]

    sync._sync_activity()

    entry_id, batch = service.batch_sync_activity.call_args.args
    assert entry_id == 101
    [sample] = batch["samples"]
    # Exactly the backend ActivitySampleCreate fields:
    assert sample == {
        "recorded_at": "2026-08-31T12:00:00+00:00",
        "keyboard_strokes": 120,
        "mouse_clicks": 35,
        "mouse_movements": 900,
        "activity_percentage": 75,
        "client_event_id": "sample-1",
    }
    cache.complete_activity_samples.assert_called_once_with(["sample-1"])


def test_unwanted_event_upload_completes_on_success_and_retries_on_failure():
    sync, cache, service = _sync_with_mocks()
    event = {
        "id": "evt-1", "time_entry_id": 101, "activity_type": "repeated_key",
        "key_or_action": "ctrl", "occurrence_count": 15, "alerted": 1,
        "alert_count": 1, "recorded_at": "2026-08-31T12:00:00+00:00",
        "retry_count": 0,
    }
    cache.get_pending_unwanted_activity.return_value = [event]

    sync._sync_unwanted_activity()
    entry_id, payload = service.record_unwanted_activity.call_args.args
    assert entry_id == 101
    assert payload["client_event_id"] == "evt-1"
    assert payload["alerted"] is True
    cache.complete_unwanted_activity.assert_called_once_with(["evt-1"])

    service.record_unwanted_activity.side_effect = Exception("boom")
    cache.complete_unwanted_activity.reset_mock()
    sync._sync_unwanted_activity()
    cache.fail_unwanted_activity.assert_called_once_with(["evt-1"])
    cache.complete_unwanted_activity.assert_not_called()


def test_adjustment_upload_carries_the_idempotency_key():
    sync, cache, service = _sync_with_mocks()
    cache.get_pending_adjustments.return_value = [{
        "id": "adj-1", "time_entry_id": 101, "adjustment_seconds": -600,
        "reason": "3 occurrences", "source_activity_type": "repeated_key",
        "source_key_or_action": "ctrl", "source_client_event_id": "evt-1",
        "recorded_at": "2026-08-31T12:00:00+00:00", "retry_count": 0,
    }]

    sync._sync_adjustments()

    entry_id, payload = service.record_adjustment.call_args.args
    assert entry_id == 101
    assert payload["adjustment_seconds"] == -600
    assert payload["client_event_id"] == "adj-1"
    assert payload["source_client_event_id"] == "evt-1"
    cache.complete_adjustments.assert_called_once_with(["adj-1"])


def test_drains_are_guarded_no_ops_when_service_lacks_the_methods():
    """The long-standing probe-by-name contract: a service object without
    these methods (older builds, partial test doubles) must be skipped
    silently, not crash the sync loop."""
    cache = MagicMock()
    bare_service = object()
    runtime = MagicMock()
    runtime.queue_floor_generation = 0
    sync = SyncService(runtime, cache, bare_service, MagicMock())

    sync._sync_activity()
    sync._sync_unwanted_activity()
    sync._sync_adjustments()
    cache.get_pending_activity_samples.assert_not_called()
    cache.get_pending_unwanted_activity.assert_not_called()
    cache.get_pending_adjustments.assert_not_called()
