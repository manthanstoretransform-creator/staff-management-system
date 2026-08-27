import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.schemas.projects_report import BillableFilter, ProjectsReportResponse
from app.services.projects_report import ProjectsReportService


class ProjectsReportServiceTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=54, organization_id=1)

    def test_invalid_date_range_raises_400(self):
        with self.assertRaises(HTTPException) as error:
            ProjectsReportService.build(
                None, self.user, date(2026, 8, 27), date(2026, 8, 1), None, None, None
            )
        self.assertEqual(error.exception.status_code, 400)

    def test_combines_auto_and_approved_manual_hours_per_project(self):
        with patch("app.services.projects_report.ProjectsReportRepository.eligible_projects",
                   return_value={1: "Alpha", 2: "Beta"}), \
             patch("app.services.projects_report.ProjectsReportRepository.hours_by_project",
                   return_value={1: 3600}), \
             patch("app.services.projects_report.ProjectsReportRepository.manual_hours_by_project",
                   return_value={1: 1800, 2: 7200}), \
             patch("app.services.projects_report.ProjectsReportRepository.activity_by_project",
                   return_value={}), \
             patch("app.services.projects_report.ProjectsReportRepository.distinct_member_ids",
                   return_value={10, 11}):
            response = ProjectsReportService.build(
                None, self.user, date(2026, 8, 1), date(2026, 8, 27), None, None, None
            )
        validated = ProjectsReportResponse.model_validate(response)
        by_id = {p.project_id: p for p in validated.projects}
        self.assertEqual(by_id[1].tracked_seconds, 5400)  # 3600 auto + 1800 approved manual
        self.assertEqual(by_id[2].tracked_seconds, 7200)  # manual-only project still included
        self.assertEqual(validated.summary.total_tracked_seconds, 12600)
        self.assertEqual(validated.summary.total_members, 2)
        self.assertEqual(validated.summary.total_projects, 2)

    def test_zero_data_project_excluded_from_results(self):
        with patch("app.services.projects_report.ProjectsReportRepository.eligible_projects",
                   return_value={1: "Alpha", 2: "Silent"}), \
             patch("app.services.projects_report.ProjectsReportRepository.hours_by_project",
                   return_value={1: 3600}), \
             patch("app.services.projects_report.ProjectsReportRepository.manual_hours_by_project",
                   return_value={}), \
             patch("app.services.projects_report.ProjectsReportRepository.activity_by_project",
                   return_value={}), \
             patch("app.services.projects_report.ProjectsReportRepository.distinct_member_ids",
                   return_value={10}):
            response = ProjectsReportService.build(
                None, self.user, date(2026, 8, 1), date(2026, 8, 27), None, None, None
            )
        project_ids = {p["project_id"] for p in response["projects"]}
        self.assertEqual(project_ids, {1})
        self.assertEqual(response["summary"]["total_projects"], 1)

    def test_activity_percentage_is_sample_weighted_across_projects(self):
        with patch("app.services.projects_report.ProjectsReportRepository.eligible_projects",
                   return_value={1: "Alpha", 2: "Beta"}), \
             patch("app.services.projects_report.ProjectsReportRepository.hours_by_project",
                   return_value={1: 3600, 2: 3600}), \
             patch("app.services.projects_report.ProjectsReportRepository.manual_hours_by_project",
                   return_value={}), \
             patch("app.services.projects_report.ProjectsReportRepository.activity_by_project",
                   return_value={1: (80.0, 1), 2: (40.0, 9)}), \
             patch("app.services.projects_report.ProjectsReportRepository.distinct_member_ids",
                   return_value={10}):
            response = ProjectsReportService.build(
                None, self.user, date(2026, 8, 1), date(2026, 8, 27), None, None, None
            )
        # weighted: (80*1 + 40*9) / 10 = 44.0, not the naive per-project average of 60.0
        self.assertEqual(response["summary"]["average_activity_percentage"], 44.0)

    def test_billing_type_forwarded_as_is_billable_flag(self):
        with patch("app.services.projects_report.ProjectsReportRepository.eligible_projects",
                   return_value={}) as eligible, \
             patch("app.services.projects_report.ProjectsReportRepository.hours_by_project", return_value={}), \
             patch("app.services.projects_report.ProjectsReportRepository.manual_hours_by_project", return_value={}), \
             patch("app.services.projects_report.ProjectsReportRepository.activity_by_project", return_value={}), \
             patch("app.services.projects_report.ProjectsReportRepository.distinct_member_ids", return_value=set()):
            ProjectsReportService.build(
                None, self.user, date(2026, 8, 1), date(2026, 8, 27), None, None, BillableFilter.non_billable
            )
        self.assertEqual(eligible.call_args.args[3], False)

    def test_empty_result_when_nothing_matches(self):
        with patch("app.services.projects_report.ProjectsReportRepository.eligible_projects",
                   return_value={}), \
             patch("app.services.projects_report.ProjectsReportRepository.hours_by_project", return_value={}), \
             patch("app.services.projects_report.ProjectsReportRepository.manual_hours_by_project", return_value={}), \
             patch("app.services.projects_report.ProjectsReportRepository.activity_by_project", return_value={}), \
             patch("app.services.projects_report.ProjectsReportRepository.distinct_member_ids", return_value=set()):
            response = ProjectsReportService.build(
                None, self.user, date(2026, 8, 1), date(2026, 8, 27), [999], [999], None
            )
        self.assertEqual(response["projects"], [])
        self.assertEqual(response["summary"]["total_projects"], 0)
        self.assertEqual(response["summary"]["average_activity_percentage"], None)


if __name__ == "__main__":
    unittest.main()
