import unittest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from datetime import datetime

from app.models.user import User
from app.models.time_entry import TimeEntry
from app.schemas.time_entry_app_usage import AppUsageCreate, AppUsageBatchCreate
from app.services.time_entry_app_usage import TimeEntryAppUsageService

class TestTimeEntryAppUsageService(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.current_user = User(id=1, organization_id=10, permissions={"time_entries:view_all": False})
        
        self.active_time_entry = TimeEntry(
            id=100,
            organization_id=10,
            user_id=1,
            status="running",
            end_time=None
        )

    @patch("app.repositories.time_entry.TimeEntryRepository.get_by_id")
    @patch("app.repositories.time_entry_app_usage.TimeEntryAppUsageRepository.create")
    def test_record_usage_success(self, mock_create, mock_get_by_id):
        mock_get_by_id.return_value = self.active_time_entry
        mock_create.return_value = MagicMock()

        payload = AppUsageCreate(
            application_name="VS Code",
            window_title="main.py",
            duration_seconds=30
        )

        TimeEntryAppUsageService.record_usage(self.db, 100, payload, self.current_user)
        
        mock_create.assert_called_once_with(
            db=self.db,
            organization_id=10,
            time_entry_id=100,
            application_name="VS Code",
            window_title="main.py",
            duration_seconds=30,
            recorded_at=None
        )

    @patch("app.repositories.time_entry.TimeEntryRepository.get_by_id")
    def test_record_usage_time_entry_not_found(self, mock_get_by_id):
        mock_get_by_id.return_value = None

        payload = AppUsageCreate(application_name="VS Code", duration_seconds=30)
        with self.assertRaises(HTTPException) as context:
            TimeEntryAppUsageService.record_usage(self.db, 999, payload, self.current_user)

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail, "Time entry not found")

    @patch("app.repositories.time_entry.TimeEntryRepository.get_by_id")
    def test_record_usage_organization_mismatch(self, mock_get_by_id):
        mismatch_time_entry = TimeEntry(id=100, organization_id=99, user_id=1, status="running")
        mock_get_by_id.return_value = mismatch_time_entry

        payload = AppUsageCreate(application_name="VS Code", duration_seconds=30)
        with self.assertRaises(HTTPException) as context:
            TimeEntryAppUsageService.record_usage(self.db, 100, payload, self.current_user)

        self.assertEqual(context.exception.status_code, 404)

    @patch("app.repositories.time_entry.TimeEntryRepository.get_by_id")
    def test_record_usage_user_mismatch(self, mock_get_by_id):
        other_user_time_entry = TimeEntry(id=100, organization_id=10, user_id=99, status="running")
        mock_get_by_id.return_value = other_user_time_entry

        payload = AppUsageCreate(application_name="VS Code", duration_seconds=30)
        with self.assertRaises(HTTPException) as context:
            TimeEntryAppUsageService.record_usage(self.db, 100, payload, self.current_user)

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(context.exception.detail, "Cannot record app usage for another user's time entry")

    @patch("app.repositories.time_entry.TimeEntryRepository.get_by_id")
    def test_record_usage_stopped_timer(self, mock_get_by_id):
        stopped_time_entry = TimeEntry(id=100, organization_id=10, user_id=1, status="stopped", end_time=datetime.now())
        mock_get_by_id.return_value = stopped_time_entry

        payload = AppUsageCreate(application_name="VS Code", duration_seconds=30)
        with self.assertRaises(HTTPException) as context:
            TimeEntryAppUsageService.record_usage(self.db, 100, payload, self.current_user)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "Cannot record app usage for a stopped time entry")

    @patch("app.repositories.time_entry.TimeEntryRepository.get_by_id")
    @patch("app.repositories.time_entry_app_usage.TimeEntryAppUsageRepository.create_batch")
    def test_batch_record_usage_success(self, mock_create_batch, mock_get_by_id):
        mock_get_by_id.return_value = self.active_time_entry
        mock_create_batch.return_value = [MagicMock(), MagicMock()]

        records = [
            AppUsageCreate(application_name="VS Code", duration_seconds=30),
            AppUsageCreate(application_name="Slack", duration_seconds=15)
        ]
        payload = AppUsageBatchCreate(records=records)

        count, _ = TimeEntryAppUsageService.batch_record_usage(self.db, 100, payload, self.current_user)
        self.assertEqual(count, 2)
        mock_create_batch.assert_called_once()

    @patch("app.repositories.time_entry.TimeEntryRepository.get_by_id")
    def test_batch_record_usage_empty(self, mock_get_by_id):
        payload = AppUsageBatchCreate(records=[])
        with self.assertRaises(HTTPException) as context:
            TimeEntryAppUsageService.batch_record_usage(self.db, 100, payload, self.current_user)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "Batch request cannot be empty")

    @patch("app.repositories.time_entry.TimeEntryRepository.get_by_id")
    @patch("app.repositories.time_entry_app_usage.TimeEntryAppUsageRepository.get_summary_by_entry")
    def test_get_summary_unprivileged_employee(self, mock_get_summary, mock_get_by_id):
        mock_get_by_id.return_value = self.active_time_entry
        mock_get_summary.return_value = [("VS Code", 60), ("Slack", 40)]

        total, apps = TimeEntryAppUsageService.get_summary(self.db, 100, self.current_user)
        
        self.assertEqual(total, 100)
        self.assertEqual(len(apps), 2)
        self.assertEqual(apps[0]["percentage"], 60.0)
        self.assertEqual(apps[1]["percentage"], 40.0)

    @patch("app.repositories.time_entry.TimeEntryRepository.get_by_id")
    def test_get_summary_access_denied_other_user(self, mock_get_by_id):
        other_user_time_entry = TimeEntry(id=100, organization_id=10, user_id=99, status="running")
        mock_get_by_id.return_value = other_user_time_entry

        with self.assertRaises(HTTPException) as context:
            TimeEntryAppUsageService.get_summary(self.db, 100, self.current_user)

        self.assertEqual(context.exception.status_code, 404)

    @patch("app.repositories.time_entry.TimeEntryRepository.get_by_id")
    @patch("app.repositories.time_entry_app_usage.TimeEntryAppUsageRepository.get_summary_by_entry")
    def test_get_summary_admin_view_all(self, mock_get_summary, mock_get_by_id):
        other_user_time_entry = TimeEntry(id=100, organization_id=10, user_id=99, status="running")
        mock_get_by_id.return_value = other_user_time_entry
        mock_get_summary.return_value = [("Chrome", 30)]
        
        admin_user = User(id=2, organization_id=10, permissions={"time_entries:view_all": True})

        total, apps = TimeEntryAppUsageService.get_summary(self.db, 100, admin_user)
        self.assertEqual(total, 30)
        self.assertEqual(apps[0]["application_name"], "Chrome")
        self.assertEqual(apps[0]["percentage"], 100.0)
