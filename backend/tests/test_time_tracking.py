import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.schemas.time_tracking import TimeTrackingDetailResponse, TimeTrackingListResponse
from app.services.time_tracking import TimeTrackingService


class TimeTrackingTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(
            id=10,
            organization_id=3,
            name="Employee",
            email="employee@example.com",
            designation="Developer",
            role_name="employee",
            permissions={"time_entries:view_all": True},
        )

    def test_date_bounds(self):
        self.assertEqual(TimeTrackingService.date_bounds("today", None, None, None), (date.today(), date.today()))
        self.assertEqual(
            TimeTrackingService.date_bounds(None, None, date(2026, 8, 1), date(2026, 8, 26)),
            (date(2026, 8, 1), date(2026, 8, 26)),
        )

    def test_invalid_date_filter(self):
        with self.assertRaises(HTTPException) as error:
            TimeTrackingService.date_bounds(None, None, date(2026, 8, 27), date(2026, 8, 26))
        self.assertEqual(error.exception.status_code, 400)

    def test_list_serializes_aggregated_duration(self):
        row = {
            "employee_id": 10,
            "name": "Employee",
            "email": "employee@example.com",
            "designation": "Developer",
            "work_date": date(2026, 8, 26),
            "start_time": datetime(2026, 8, 26, 10, tzinfo=timezone.utc),
            "end_time": datetime(2026, 8, 26, 16, tzinfo=timezone.utc),
            "total_seconds": 5 * 3600,
        }
        with patch("app.services.time_tracking.TimeTrackingRepository.list_daily_totals", return_value=([row], 1)):
            response = TimeTrackingService.list_daily(
                None, self.user, None, date(2026, 8, 26), None, None, None, 1, 50
            )
        validated = TimeTrackingListResponse.model_validate(response)
        self.assertEqual(validated.items[0].total_hours, "5h 0m")
        self.assertEqual(validated.items[0].total_seconds, 5 * 3600)

    def test_detail_aggregates_multiple_tasks_and_running_entry(self):
        project = SimpleNamespace(id=92, project_name="Alpha")
        task = SimpleNamespace(id=185, task_name="Setup")
        project_status = SimpleNamespace(id=1, name="Active", color="#3B82F6")
        task_status = SimpleNamespace(id=2, name="In Progress", color="#F59E0B")
        first = SimpleNamespace(
            id=1001,
            start_time=datetime(2026, 8, 26, 10, tzinfo=timezone.utc),
            end_time=datetime(2026, 8, 26, 12, tzinfo=timezone.utc),
        )
        running = SimpleNamespace(
            id=1002,
            start_time=datetime(2026, 8, 26, 13, tzinfo=timezone.utc),
            end_time=None,
        )
        rows = [(first, project, task, project_status, task_status, 7200), (running, project, task, project_status, task_status, 3600)]
        with patch("app.services.time_tracking.TimeTrackingRepository.get_employee", return_value=self.user), \
             patch("app.services.time_tracking.TimeTrackingRepository.detail_entries", return_value=rows):
            response = TimeTrackingService.detail(
                None, self.user, 10, None, date(2026, 8, 26), None, None
            )
        validated = TimeTrackingDetailResponse.model_validate(response)
        self.assertEqual(validated.summary.total_seconds, 10800)
        self.assertEqual(validated.projects[0].tasks[0].total_seconds, 10800)
        self.assertTrue(validated.projects[0].tasks[0].entries[1].is_running)

    def test_unprivileged_employee_filter_is_forbidden(self):
        self.user.permissions = {}
        with self.assertRaises(HTTPException) as error:
            TimeTrackingService.list_daily(None, self.user, "today", None, None, None, 11, 1, 50)
        self.assertEqual(error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
