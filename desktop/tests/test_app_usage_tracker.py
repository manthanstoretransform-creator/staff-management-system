"""
Application-usage tracking tests.

Ported from the original suite when `tracking.app_usage_tracker.AppUsageTracker`
and `sync.sync_queue.SyncQueue` were replaced by `AppUsageService` and
`SyncService`. The behaviour asserted is the same — sample the foreground
window, flush a segment when it changes or when the cap is reached, batch the
segments for upload, retry on failure — only the ownership changed.
"""
from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock, patch

from background_services.activity.app_usage_service import AppUsageService


class StubRuntime:
    def __init__(self):
        self.timer = MagicMock()
        self.timer.active_session.return_value = {"entry_id": 101}


class TestAppUsageService(unittest.TestCase):
    def setUp(self):
        self.cache = MagicMock()
        self.service = AppUsageService(StubRuntime(), self.cache)

    @patch("background_services.activity.app_usage_service.get_active_window_info")
    def test_segment_is_saved_when_the_foreground_window_changes(self, active_window):
        active_window.return_value = ("VS Code", "main.py")
        self.service.start_tracker({"entry_id": 101})
        self.service.tick()  # opens the first segment

        self.assertEqual(self.service._current_app, "VS Code")
        self.assertEqual(self.service._current_title, "main.py")

        self.service._segment_start = time.monotonic() - 15.0
        active_window.return_value = ("Chrome", "Dashboard")
        self.service.tick()

        self.cache.save_app_usage.assert_called_once()
        kwargs = self.cache.save_app_usage.call_args.kwargs
        self.assertEqual(kwargs["time_entry_id"], 101)
        self.assertEqual(kwargs["application_name"], "VS Code")
        self.assertEqual(kwargs["window_title"], "main.py")
        self.assertGreaterEqual(kwargs["duration_seconds"], 15)

    @patch("background_services.activity.app_usage_service.get_active_window_info")
    def test_long_unbroken_segment_is_flushed_at_the_cap(self, active_window):
        """
        A long session in one application must still produce incremental
        records, so a crash cannot lose an hour of usage in one row.
        """
        active_window.return_value = ("VS Code", "main.py")
        self.service.start_tracker({"entry_id": 101})
        self.service.tick()

        self.service._segment_start = (
            time.monotonic() - AppUsageService.MAX_SEGMENT_SECONDS - 5
        )
        self.service.tick()

        self.cache.save_app_usage.assert_called_once()

    def test_stopping_finalises_the_open_segment(self):
        self.service._tracking = True
        self.service._entry_id = 101
        self.service._current_app = "VS Code"
        self.service._current_title = "main.py"
        self.service._segment_start = time.monotonic() - 10.0
        self.service._segment_recorded_at = "2026-08-24T10:00:00Z"

        self.service.stop_tracker()

        self.cache.save_app_usage.assert_called_once()
        self.assertIsNone(self.service._entry_id)

    @patch("background_services.activity.app_usage_service.get_active_window_info")
    def test_nothing_is_recorded_when_no_session_is_tracked(self, active_window):
        active_window.return_value = ("VS Code", "main.py")
        self.service.tick()
        self.cache.save_app_usage.assert_not_called()


class TestAppUsageBatchSync(unittest.TestCase):
    """The batching/retry behaviour, now owned by SyncService."""

    def setUp(self):
        from background_services.sync.sync_service import SyncService

        self.cache = MagicMock()
        self.time_entry_service = MagicMock()
        self.task_service = MagicMock()
        runtime = MagicMock()
        runtime.queue_floor_generation = 0
        self.sync = SyncService(
            runtime, self.cache, self.time_entry_service, self.task_service
        )

    def test_records_are_batched_per_time_entry(self):
        self.cache.get_pending_app_usage.return_value = [
            {"id": "rec-1", "time_entry_id": 101, "application_name": "VS Code",
             "window_title": "main.py", "duration_seconds": 30,
             "recorded_at": "2026-08-24T10:00:00Z"},
            {"id": "rec-2", "time_entry_id": 101, "application_name": "Chrome",
             "window_title": "Dashboard", "duration_seconds": 15,
             "recorded_at": "2026-08-24T10:00:30Z"},
        ]

        self.sync._sync_app_usage()

        self.cache.mark_app_usage_processing.assert_called_once_with(["rec-1", "rec-2"])
        self.time_entry_service.batch_sync_app_usage.assert_called_once()
        self.cache.complete_app_usage.assert_called_once_with(["rec-1", "rec-2"])

    def test_failures_are_retried_not_dropped(self):
        self.cache.get_pending_app_usage.return_value = [
            {"id": "rec-1", "time_entry_id": 101, "application_name": "VS Code",
             "window_title": "main.py", "duration_seconds": 30,
             "recorded_at": "2026-08-24T10:00:00Z"},
        ]
        self.time_entry_service.batch_sync_app_usage.side_effect = Exception("API Error")

        self.sync._sync_app_usage()

        self.cache.mark_app_usage_processing.assert_called_once()
        self.cache.fail_app_usage.assert_called_once_with(["rec-1"], "API Error")
        self.cache.complete_app_usage.assert_not_called()
