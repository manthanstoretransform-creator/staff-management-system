import unittest
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.schemas.reports import BillableFilter, ReportDimension, UsageType
from app.services.reports import ReportsService, _weighted_average


class WeightedAverageTests(unittest.TestCase):
    def test_weighted_by_sample_count(self):
        # (80*1 + 40*9) / 10 = 44.0, not the naive per-item average of 60.0
        self.assertEqual(_weighted_average([(80.0, 1), (40.0, 9)]), 44.0)

    def test_none_when_no_samples(self):
        self.assertIsNone(_weighted_average([(None, 0), (None, 0)]))

    def test_skips_zero_count_pairs(self):
        self.assertEqual(_weighted_average([(50.0, 0), (70.0, 2)]), 70.0)


class ReportsServiceCommonTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=54, organization_id=1)

    def test_invalid_date_range_raises_400(self):
        with self.assertRaises(HTTPException) as error:
            ReportsService.build_grouped(
                None, self.user, ReportDimension.projects, date(2026, 8, 27), date(2026, 8, 1),
                None, None, None, UsageType.app,
            )
        self.assertEqual(error.exception.status_code, 400)

    def test_detailed_logs_invalid_date_range_raises_400(self):
        with self.assertRaises(HTTPException) as error:
            ReportsService.build_detailed_logs(
                None, self.user, ReportDimension.projects, date(2026, 8, 27), date(2026, 8, 1),
                None, None, None, UsageType.app, None, "date", True, 1, 50,
            )
        self.assertEqual(error.exception.status_code, 400)


class GroupedProjectsTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=54, organization_id=1)

    def test_zero_data_project_excluded_and_meta_label_from_triples(self):
        with patch("app.services.reports.ReportsRepository.eligible_projects",
                   return_value={1: "Alpha", 2: "Silent"}), \
             patch("app.services.reports.ReportsRepository.session_seconds_by",
                   side_effect=[{1: 3600}, {}]), \
             patch("app.services.reports.ReportsRepository.session_activity_by",
                   return_value={1: (80.0, 4)}), \
             patch("app.services.reports.ReportsRepository.session_triples",
                   return_value={(1, 10, 100), (1, 11, 101)}), \
             patch("app.services.reports.ReportsRepository.session_entry_count", return_value=7):
            response = ReportsService.build_grouped(
                None, self.user, ReportDimension.projects, date(2026, 8, 1), date(2026, 8, 27),
                None, None, None, UsageType.app,
            )
        self.assertEqual(len(response["grouped_data"]), 1)
        item = response["grouped_data"][0]
        self.assertEqual(item["id"], 1)
        self.assertEqual(item["meta_label"], "2 members · 2 tasks")
        self.assertEqual(response["summary"]["total_projects"], 1)
        self.assertEqual(response["summary"]["total_members"], 2)
        self.assertEqual(response["summary"]["total_entries"], 7)
        self.assertEqual(response["summary"]["average_activity_percentage"], 80.0)

    def test_session_seconds_by_called_with_project_id_grouping(self):
        with patch("app.services.reports.ReportsRepository.eligible_projects", return_value={1: "Alpha"}), \
             patch("app.services.reports.ReportsRepository.session_seconds_by", return_value={}) as seconds, \
             patch("app.services.reports.ReportsRepository.session_activity_by", return_value={}), \
             patch("app.services.reports.ReportsRepository.session_triples", return_value=set()), \
             patch("app.services.reports.ReportsRepository.session_entry_count", return_value=0):
            ReportsService.build_grouped(
                None, self.user, ReportDimension.projects, date(2026, 8, 1), date(2026, 8, 27),
                None, None, None, UsageType.app,
            )
        self.assertEqual(seconds.call_args.args[-1], "project_id")


class GroupedMembersTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=54, organization_id=1)

    def test_member_meta_label_and_name_lookup(self):
        with patch("app.services.reports.ReportsRepository.eligible_projects", return_value={1: "Alpha", 2: "Beta"}), \
             patch("app.services.reports.ReportsRepository.session_seconds_by", return_value={10: 7200}), \
             patch("app.services.reports.ReportsRepository.session_activity_by", return_value={10: (70.0, 2)}), \
             patch("app.services.reports.ReportsRepository.session_triples",
                   return_value={(1, 10, 100), (2, 10, 101), (2, 10, 102)}), \
             patch("app.services.reports.ReportsRepository.users_lookup", return_value={10: ("Ada", "employee")}), \
             patch("app.services.reports.ReportsRepository.session_entry_count", return_value=3):
            response = ReportsService.build_grouped(
                None, self.user, ReportDimension.members, date(2026, 8, 1), date(2026, 8, 27),
                None, None, None, UsageType.app,
            )
        item = response["grouped_data"][0]
        self.assertEqual(item["name"], "Ada")
        self.assertEqual(item["meta_label"], "2 projects, 3 tasks")
        self.assertEqual(response["summary"]["total_members"], 1)


class GroupedAppsTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=54, organization_id=1)

    def test_uses_usage_repository_methods_for_apps_dimension(self):
        with patch("app.services.reports.ReportsRepository.eligible_projects", return_value={1: "Alpha"}), \
             patch("app.services.reports.ReportsRepository.app_usage_seconds_by_name",
                   return_value={"VS Code": 600}) as seconds, \
             patch("app.services.reports.ReportsRepository.app_usage_activity_by_name",
                   return_value={"VS Code": (90.0, 1)}), \
             patch("app.services.reports.ReportsRepository.app_usage_member_counts_by_name",
                   return_value={"VS Code": 2}), \
             patch("app.services.reports.ReportsRepository.app_usage_distinct_member_ids",
                   return_value={10, 11}), \
             patch("app.services.reports.ReportsRepository.app_usage_entry_count", return_value=5):
            response = ReportsService.build_grouped(
                None, self.user, ReportDimension.apps, date(2026, 8, 1), date(2026, 8, 27),
                None, None, None, UsageType.app,
            )
        self.assertEqual(seconds.call_args.args[-1], "app")
        item = response["grouped_data"][0]
        self.assertEqual(item["id"], "VS Code")
        self.assertEqual(item["meta_label"], "2 members")
        self.assertEqual(response["summary"]["total_apps"], 1)

    def test_url_usage_type_forwarded(self):
        with patch("app.services.reports.ReportsRepository.eligible_projects", return_value={1: "Alpha"}), \
             patch("app.services.reports.ReportsRepository.app_usage_seconds_by_name", return_value={}) as seconds, \
             patch("app.services.reports.ReportsRepository.app_usage_activity_by_name", return_value={}), \
             patch("app.services.reports.ReportsRepository.app_usage_member_counts_by_name", return_value={}), \
             patch("app.services.reports.ReportsRepository.app_usage_distinct_member_ids", return_value=set()), \
             patch("app.services.reports.ReportsRepository.app_usage_entry_count", return_value=0):
            ReportsService.build_grouped(
                None, self.user, ReportDimension.apps, date(2026, 8, 1), date(2026, 8, 27),
                None, None, None, UsageType.url,
            )
        self.assertEqual(seconds.call_args.args[-1], "url")


class DetailedLogsTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=54, organization_id=1)

    def test_session_dimension_maps_rows_with_null_app_and_url(self):
        row = SimpleNamespace(
            id="te-1", work_date=date(2026, 8, 20), member_id=10, member_name="Ada", role="employee",
            project_id=1, project_name="Alpha", task_id=100, task_name="Design",
            tracked_seconds=3600, activity_percentage=72.5,
        )
        with patch("app.services.reports.ReportsRepository.eligible_projects", return_value={1: "Alpha"}), \
             patch("app.services.reports.ReportsRepository.session_detailed_logs", return_value=([row], 1)):
            response = ReportsService.build_detailed_logs(
                None, self.user, ReportDimension.projects, date(2026, 8, 1), date(2026, 8, 27),
                None, None, None, UsageType.app, None, "date", True, 1, 50,
            )
        item = response["items"][0]
        self.assertIsNone(item["app"])
        self.assertIsNone(item["url"])
        self.assertEqual(item["tracked_hours"], 1.0)
        self.assertEqual(response["pagination"], {"page": 1, "limit": 50, "total": 1, "total_pages": 1})

    def test_apps_dimension_maps_name_onto_app_field(self):
        row = SimpleNamespace(
            id="au-1", work_date=date(2026, 8, 20), member_id=10, member_name="Ada", role="employee",
            project_id=1, project_name="Alpha", task_id=100, task_name="Design",
            name="VS Code", tracked_seconds=120, activity_percentage=None,
        )
        with patch("app.services.reports.ReportsRepository.eligible_projects", return_value={1: "Alpha"}), \
             patch("app.services.reports.ReportsRepository.app_usage_detailed_logs", return_value=([row], 1)):
            response = ReportsService.build_detailed_logs(
                None, self.user, ReportDimension.apps, date(2026, 8, 1), date(2026, 8, 27),
                None, None, None, UsageType.app, None, "date", True, 1, 50,
            )
        item = response["items"][0]
        self.assertEqual(item["app"], "VS Code")
        self.assertIsNone(item["url"])

    def test_apps_dimension_url_usage_maps_name_onto_url_field(self):
        row = SimpleNamespace(
            id="uu-1", work_date=date(2026, 8, 20), member_id=10, member_name="Ada", role="employee",
            project_id=1, project_name="Alpha", task_id=100, task_name="Design",
            name="github.com", tracked_seconds=60, activity_percentage=None,
        )
        with patch("app.services.reports.ReportsRepository.eligible_projects", return_value={1: "Alpha"}), \
             patch("app.services.reports.ReportsRepository.app_usage_detailed_logs", return_value=([row], 1)):
            response = ReportsService.build_detailed_logs(
                None, self.user, ReportDimension.apps, date(2026, 8, 1), date(2026, 8, 27),
                None, None, None, UsageType.url, None, "date", True, 1, 50,
            )
        item = response["items"][0]
        self.assertIsNone(item["app"])
        self.assertEqual(item["url"], "github.com")

    def test_pagination_offset_computed_from_page_and_limit(self):
        with patch("app.services.reports.ReportsRepository.eligible_projects", return_value={1: "Alpha"}), \
             patch("app.services.reports.ReportsRepository.session_detailed_logs", return_value=([], 0)) as query:
            ReportsService.build_detailed_logs(
                None, self.user, ReportDimension.projects, date(2026, 8, 1), date(2026, 8, 27),
                None, None, None, UsageType.app, None, "date", True, 3, 20,
            )
        self.assertEqual(query.call_args.args[-2], 40)  # offset = (3-1)*20
        self.assertEqual(query.call_args.args[-1], 20)  # limit


class ProjectTaskSummaryTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=54, organization_id=1)
        self.project = SimpleNamespace(
            id=1, project_name="Alpha", created_at=datetime(2026, 8, 1), status_id=2,
        )
        self.tracked_task = SimpleNamespace(
            id=100, task_name="Design", created_at=datetime(2026, 8, 2), project_id=1,
        )
        self.untracked_task = SimpleNamespace(
            id=101, task_name="Untouched", created_at=datetime(2026, 8, 3), project_id=1,
        )

    def test_date_and_date_range_together_raises_400(self):
        with self.assertRaises(HTTPException) as error:
            ReportsService.build_project_task_summary(
                None, self.user, 1, 5, None, date(2026, 8, 1), date(2026, 8, 1), date(2026, 8, 5),
            )
        self.assertEqual(error.exception.status_code, 400)

    def test_start_date_without_end_date_raises_400(self):
        with self.assertRaises(HTTPException) as error:
            ReportsService.build_project_task_summary(
                None, self.user, 1, 5, None, None, date(2026, 8, 1), None,
            )
        self.assertEqual(error.exception.status_code, 400)

    def test_start_date_after_end_date_raises_400(self):
        with self.assertRaises(HTTPException) as error:
            ReportsService.build_project_task_summary(
                None, self.user, 1, 5, None, None, date(2026, 8, 27), date(2026, 8, 1),
            )
        self.assertEqual(error.exception.status_code, 400)

    def test_invalid_project_id_raises_400(self):
        with patch("app.services.reports.ReportsRepository.existing_project_ids", return_value={1}):
            with self.assertRaises(HTTPException) as error:
                ReportsService.build_project_task_summary(
                    None, self.user, 1, 5, [1, 999], None, None, None,
                )
        self.assertEqual(error.exception.status_code, 400)

    def test_no_date_filter_uses_all_time_range(self):
        with patch("app.services.reports.ReportsRepository.paginated_projects", return_value=([self.project], 1)), \
             patch("app.services.reports.ReportsRepository.session_seconds_by", return_value={}) as seconds, \
             patch("app.services.reports.ReportsRepository.active_tasks_by_project", return_value={}), \
             patch("app.services.reports.ReportsRepository.project_statuses_lookup", return_value={}):
            ReportsService.build_project_task_summary(None, self.user, 1, 5, None, None, None, None)
        start_date, end_date = seconds.call_args_list[0].args[6], seconds.call_args_list[0].args[7]
        self.assertEqual(start_date, ReportsService._EPOCH_DATE)
        self.assertEqual(end_date, ReportsService._FAR_FUTURE_DATE)

    def test_project_with_tasks_including_zero_hour_task(self):
        with patch("app.services.reports.ReportsRepository.paginated_projects", return_value=([self.project], 1)), \
             patch("app.services.reports.ReportsRepository.session_seconds_by",
                   side_effect=[{1: 7200}, {100: 7200}]), \
             patch("app.services.reports.ReportsRepository.active_tasks_by_project",
                   return_value={1: [self.tracked_task, self.untracked_task]}), \
             patch("app.services.reports.ReportsRepository.project_statuses_lookup", return_value={}):
            response = ReportsService.build_project_task_summary(
                None, self.user, 1, 5, None, date(2026, 8, 1), None, None,
            )

        project_item = response["projects"][0]
        self.assertEqual(project_item["total_task_hours"], 2.0)
        self.assertEqual(project_item["total_task_count"], 2)
        self.assertEqual(len(project_item["tasks"]), 2)
        tracked, untracked = project_item["tasks"]
        self.assertEqual(tracked["total_tracked_hours"], 2.0)
        # Untracked task still appears -- 0 hours, not silently dropped.
        self.assertEqual(untracked["total_tracked_hours"], 0.0)
        self.assertEqual(response["pagination"], {"page": 1, "limit": 5, "total_projects": 1, "total_pages": 1})

    def test_no_projects_on_page_returns_empty_list_not_error(self):
        with patch("app.services.reports.ReportsRepository.paginated_projects", return_value=([], 0)), \
             patch("app.services.reports.ReportsRepository.session_seconds_by", return_value={}), \
             patch("app.services.reports.ReportsRepository.active_tasks_by_project", return_value={}), \
             patch("app.services.reports.ReportsRepository.project_statuses_lookup", return_value={}):
            response = ReportsService.build_project_task_summary(None, self.user, 1, 5, None, None, None, None)
        self.assertEqual(response["projects"], [])
        self.assertEqual(response["pagination"]["total_pages"], 0)


if __name__ == "__main__":
    unittest.main()
