import unittest
from unittest.mock import MagicMock
import sys
import os

# Inject current desktop directory to sys.path so app module can be found
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.timer.engine import TimerEngine, TimerState

class TestTimerEngine(unittest.TestCase):
    """Unit test suite for the monotonic TimerEngine business logic."""

    def setUp(self) -> None:
        self.mock_time = 100.0
        # Time provider that we can control manually
        self.time_provider = lambda: self.mock_time
        self.engine = TimerEngine(time_provider=self.time_provider)

    def test_initial_state_is_idle(self) -> None:
        self.assertEqual(self.engine.state, TimerState.IDLE)
        self.assertEqual(self.engine.elapsed(), 0.0)
        self.assertIsNone(self.engine.project_id)
        self.assertIsNone(self.engine.task_id)

    def test_start_changes_state_and_records_identifiers(self) -> None:
        self.engine.start(project_id=12, task_id=34)
        
        self.assertEqual(self.engine.state, TimerState.RUNNING)
        self.assertEqual(self.engine.project_id, 12)
        self.assertEqual(self.engine.task_id, 34)

    def test_elapsed_time_increases_with_time_provider(self) -> None:
        self.engine.start(project_id=12, task_id=34)
        
        # Advance time by 5.5 seconds
        self.mock_time = 105.5
        
        self.assertEqual(self.engine.elapsed(), 5.5)

    def test_stop_changes_state_and_preserves_duration(self) -> None:
        self.engine.start(project_id=12, task_id=34)
        self.mock_time = 110.0
        
        final_elapsed = self.engine.stop()
        
        self.assertEqual(self.engine.state, TimerState.STOPPED)
        self.assertEqual(final_elapsed, 10.0)
        self.assertEqual(self.engine.elapsed(), 10.0)
        
        # Advance clock again: elapsed must NOT change since timer is stopped
        self.mock_time = 120.0
        self.assertEqual(self.engine.elapsed(), 10.0)

    def test_cannot_start_twice(self) -> None:
        self.engine.start(project_id=1, task_id=1)
        with self.assertRaises(ValueError) as context:
            self.engine.start(project_id=1, task_id=1)
        self.assertIn("already running", str(context.exception))

    def test_cannot_stop_when_not_running(self) -> None:
        with self.assertRaises(ValueError) as context:
            self.engine.stop()
        self.assertIn("not currently running", str(context.exception))

    def test_new_session_does_not_reuse_stale_data(self) -> None:
        # Run first session
        self.engine.start(project_id=1, task_id=1)
        self.mock_time = 105.0
        self.engine.stop()
        self.assertEqual(self.engine.elapsed(), 5.0)
        
        # Start second session
        self.mock_time = 200.0
        self.engine.start(project_id=2, task_id=2)
        
        # Verify elapsed starts at 0.0, and does not carry over the 5.0 seconds from first session
        self.assertEqual(self.engine.elapsed(), 0.0)
        self.assertEqual(self.engine.project_id, 2)
        self.assertEqual(self.engine.task_id, 2)
        
        self.mock_time = 203.2
        self.assertAlmostEqual(self.engine.elapsed(), 3.2)

    def test_reset_clears_engine(self) -> None:
        self.engine.start(project_id=5, task_id=6)
        self.mock_time = 115.0
        self.engine.stop()
        
        self.engine.reset()
        
        self.assertEqual(self.engine.state, TimerState.IDLE)
        self.assertEqual(self.engine.elapsed(), 0.0)
        self.assertIsNone(self.engine.project_id)
        self.assertIsNone(self.engine.task_id)

    def test_start_validation(self) -> None:
        with self.assertRaises(ValueError) as context:
            self.engine.start(project_id=0, task_id=1)
        self.assertIn("select a project", str(context.exception))

        with self.assertRaises(ValueError) as context:
            self.engine.start(project_id=1, task_id=0)
        self.assertIn("select a task", str(context.exception))

from app.api.client import ApiClient
from app.api.exceptions import ApiHttpError, ApiConnectionError, ApiError
from app.time_entries.service import TimeEntryService

class TestTimeEntryService(unittest.TestCase):
    """Unit tests for the TimeEntryService backend integration logic."""

    def setUp(self) -> None:
        self.api_client = MagicMock(spec=ApiClient)
        self.service = TimeEntryService(self.api_client)

    def test_start_time_entry_success(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 12345, "status": "running"}
        self.api_client.post.return_value = mock_response

        entry_id = self.service.start_time_entry(project_id=10, task_id=20)
        
        self.assertEqual(entry_id, 12345)
        self.api_client.post.assert_called_once_with(
            "/time-entries/start",
            json_data={
                "project_id": 10,
                "task_id": 20,
                "description": None,
                "is_billable": None
            }
        )

    def test_start_time_entry_conflict_active_timer(self) -> None:
        self.api_client.post.side_effect = ApiHttpError(
            status_code=409,
            response_body="User already has an active timer",
            message="Conflict"
        )
        
        with self.assertRaises(ApiError) as context:
            self.service.start_time_entry(project_id=10, task_id=20)
            
        self.assertIn("User already has an active timer", str(context.exception))

    def test_stop_time_entry_success(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 12345, "status": "stopped", "total_seconds": 15}
        self.api_client.post.return_value = mock_response

        result = self.service.stop_time_entry(entry_id=12345)
        
        self.assertEqual(result["status"], "stopped")
        self.api_client.post.assert_called_once_with(
            "/time-entries/12345/stop",
            json_data={"description": None},
            timeout=None
        )

    def test_stop_time_entry_not_found(self) -> None:
        self.api_client.post.side_effect = ApiHttpError(
            status_code=404,
            response_body="Active timer not found",
            message="Not Found"
        )
        
        with self.assertRaises(ApiError) as context:
            self.service.stop_time_entry(entry_id=999)
            
        self.assertIn("Active timer not found on backend", str(context.exception))

if __name__ == "__main__":
    unittest.main()

