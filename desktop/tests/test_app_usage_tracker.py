import unittest
from unittest.mock import MagicMock, patch
import time

from tracking.app_usage_tracker import AppUsageTracker
from sync.sync_queue import SyncQueue

class TestAppUsageTracker(unittest.TestCase):
    def setUp(self):
        self.local_cache = MagicMock()
        self.tracker = AppUsageTracker(self.local_cache)

    @patch("tracking.app_usage_tracker.get_active_window_info")
    def test_tracker_samples_and_saves_segment_on_stop(self, mock_active_window):
        mock_active_window.return_value = ("VS Code", "main.py")
        
        # Start tracking
        session_data = {"entry_id": 101}
        self.tracker.start_tracker(session_data)
        
        self.assertEqual(self.tracker._current_app, "VS Code")
        self.assertEqual(self.tracker._current_title, "main.py")
        
        # Simulate time passing and foreground change
        self.tracker._segment_start = time.monotonic() - 15.0
        mock_active_window.return_value = ("Chrome", "Dashboard")
        
        # Trigger sampling
        self.tracker._sample()
        
        # Assert previous segment saved
        self.local_cache.save_app_usage.assert_called_once()
        args, kwargs = self.local_cache.save_app_usage.call_args
        self.assertEqual(kwargs["time_entry_id"], 101)
        self.assertEqual(kwargs["application_name"], "VS Code")
        self.assertEqual(kwargs["window_title"], "main.py")
        self.assertGreaterEqual(kwargs["duration_seconds"], 15)

    @patch("tracking.app_usage_tracker.get_active_window_info")
    def test_tracker_flush_at_max_duration(self, mock_active_window):
        mock_active_window.return_value = ("VS Code", "main.py")
        
        self.tracker.start_tracker({"entry_id": 101})
        
        # Simulate 40 seconds elapsed (greater than MAX_ACCUMULATION = 30)
        self.tracker._segment_start = time.monotonic() - 40.0
        
        self.tracker._sample()
        
        # It should save segment even though foreground didn't change
        self.local_cache.save_app_usage.assert_called_once()

    def test_tracker_stop_finalizes_segment(self):
        self.tracker._time_entry_id = 101
        self.tracker._current_app = "VS Code"
        self.tracker._current_title = "main.py"
        self.tracker._segment_start = time.monotonic() - 10.0
        self.tracker._segment_recorded_at = "2026-08-24T10:00:00Z"
        
        self.tracker.stop_tracker()
        
        self.local_cache.save_app_usage.assert_called_once()
        self.assertIsNone(self.tracker._time_entry_id)


class TestAppUsageSyncQueue(unittest.TestCase):
    def setUp(self):
        self.cache = MagicMock()
        self.time_entry_service = MagicMock()
        self.task_service = MagicMock()
        self.sync_queue = SyncQueue(self.cache, self.time_entry_service, self.task_service)

    def test_sync_app_usage_batches_correctly(self):
        # Setup mock pending records
        self.cache.get_pending_app_usage.return_value = [
            {"id": "rec-1", "time_entry_id": 101, "application_name": "VS Code", "window_title": "main.py", "duration_seconds": 30, "recorded_at": "2026-08-24T10:00:00Z"},
            {"id": "rec-2", "time_entry_id": 101, "application_name": "Chrome", "window_title": "Dashboard", "duration_seconds": 15, "recorded_at": "2026-08-24T10:00:30Z"}
        ]
        
        self.sync_queue._sync_app_usage()
        
        # Verify SQLite status changes and API delivery
        self.cache.mark_app_usage_processing.assert_called_once_with(["rec-1", "rec-2"])
        self.time_entry_service.batch_sync_app_usage.assert_called_once()
        self.cache.complete_app_usage.assert_called_once_with(["rec-1", "rec-2"])

    def test_sync_app_usage_failures_are_retried(self):
        self.cache.get_pending_app_usage.return_value = [
            {"id": "rec-1", "time_entry_id": 101, "application_name": "VS Code", "window_title": "main.py", "duration_seconds": 30, "recorded_at": "2026-08-24T10:00:00Z"}
        ]
        # Simulate network failure
        self.time_entry_service.batch_sync_app_usage.side_effect = Exception("API Error")
        
        self.sync_queue._sync_app_usage()
        
        self.cache.mark_app_usage_processing.assert_called_once()
        self.cache.fail_app_usage.assert_called_once_with(["rec-1"], "API Error")
