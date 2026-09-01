"""Tests for the React Reports page APIs (app/react_apis/reports_page).

Two kinds of coverage here:

* Filter/shaping unit tests, matching the mock-based style of
  tests/test_reports.py -- no database required.
* SQL compilation tests, which render every report query against the
  PostgreSQL dialect. These are what catch the failure mode this feature is
  most exposed to: a join that fans rows out and silently inflates
  SUM(seconds). They assert that activity and adjustments are pre-aggregated
  to one row per time entry before being joined.
"""

import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from app.core.time_format import ist_day_end_utc, ist_day_start_utc
from app.react_apis.reports_page.repository import ReportFilters, ReportsPageRepository
from app.react_apis.reports_page.service import ReportsPageService


def _user(organization_id=1):
    return SimpleNamespace(id=54, organization_id=organization_id)


def _filters(**overrides):
    base = dict(
        organization_id=1,
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 7),
        start_time=ist_day_start_utc(date(2026, 9, 1)),
        end_time=ist_day_end_utc(date(2026, 9, 7)),
    )
    base.update(overrides)
    return ReportFilters(**base)


def _sql(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


class ResolveFiltersTests(unittest.TestCase):
    def test_default_range_is_last_seven_calendar_days_including_today(self):
        today = date.today()
        filters = ReportsPageService.resolve_filters(_user(), None, None, None, None, None)
        self.assertEqual(filters.end_date, today)
        self.assertEqual(filters.start_date, today - timedelta(days=6))
        # 7 calendar days inclusive, not 7 completed 24h periods.
        self.assertEqual((filters.end_date - filters.start_date).days, 6)

    def test_default_start_is_derived_from_an_explicit_end_date(self):
        filters = ReportsPageService.resolve_filters(_user(), None, date(2026, 9, 7), None, None, None)
        self.assertEqual(filters.start_date, date(2026, 9, 1))

    def test_end_date_bound_is_exclusive_start_of_the_next_day(self):
        filters = ReportsPageService.resolve_filters(
            _user(), date(2026, 9, 1), date(2026, 9, 7), None, None, None
        )
        self.assertEqual(filters.start_time, ist_day_start_utc(date(2026, 9, 1)))
        self.assertEqual(filters.end_time, ist_day_start_utc(date(2026, 9, 8)))

    def test_inverted_range_raises_400(self):
        with self.assertRaises(HTTPException) as error:
            ReportsPageService.resolve_filters(
                _user(), date(2026, 9, 7), date(2026, 9, 1), None, None, None
            )
        self.assertEqual(error.exception.status_code, 400)

    def test_equal_start_and_end_is_a_valid_single_day(self):
        filters = ReportsPageService.resolve_filters(
            _user(), date(2026, 9, 7), date(2026, 9, 7), None, None, None
        )
        self.assertEqual(filters.start_date, filters.end_date)

    def test_organization_comes_from_the_authenticated_user(self):
        filters = ReportsPageService.resolve_filters(_user(organization_id=99), None, None, None, None, None)
        self.assertEqual(filters.organization_id, 99)

    def test_entity_filters_are_carried_through(self):
        filters = ReportsPageService.resolve_filters(_user(), None, None, 12, 101, 102)
        self.assertEqual((filters.project_id, filters.task_id, filters.member_id), (12, 101, 102))


class ShapingTests(unittest.TestCase):
    def test_metrics_convert_seconds_to_hours_and_round_activity(self):
        row = SimpleNamespace(total_seconds=153900, avg_activity=71.3216, total_members=5, total_tasks=14)
        self.assertEqual(
            ReportsPageService._metrics(row),
            {"total_hours": 42.75, "avg_activity": 71.32, "total_members": 5, "total_tasks": 14},
        )

    def test_null_activity_stays_null_rather_than_becoming_zero(self):
        row = SimpleNamespace(total_seconds=3600, avg_activity=None, total_members=1, total_tasks=1)
        self.assertIsNone(ReportsPageService._metrics(row)["avg_activity"])

    def test_page_math(self):
        self.assertEqual(
            ReportsPageService._page([], 1, 20, 100),
            {"items": [], "page": 1, "limit": 20, "total": 100, "pages": 5},
        )
        self.assertEqual(ReportsPageService._page([], 1, 20, 41)["pages"], 3)
        self.assertEqual(ReportsPageService._page([], 1, 20, 0)["pages"], 0)

    def test_project_rows_are_named_with_project_fields(self):
        row = SimpleNamespace(id=12, name="Website Redesign", total_seconds=3600,
                              avg_activity=70.0, total_members=5, total_tasks=14)
        with patch.object(ReportsPageRepository, "projects", return_value=([row], 1)):
            response = ReportsPageService.projects(None, _filters(), None, "total_hours", "desc", 1, 20)
        self.assertEqual(response["items"][0]["project_id"], 12)
        self.assertEqual(response["items"][0]["project_name"], "Website Redesign")
        self.assertEqual(response["total"], 1)

    def test_task_rows_report_one_task_each(self):
        row = SimpleNamespace(id=101, name="Implement Login API", total_seconds=30600,
                              avg_activity=76.21, total_members=2, total_tasks=1)
        with patch.object(ReportsPageRepository, "tasks", return_value=([row], 1)):
            response = ReportsPageService.tasks(None, _filters(), None, "total_hours", "desc", 1, 20)
        item = response["items"][0]
        self.assertEqual(item["task_id"], 101)
        self.assertEqual(item["total_tasks"], 1)
        self.assertEqual(item["total_hours"], 8.5)

    def test_app_and_url_ids_are_usage_table_row_ids(self):
        app_row = SimpleNamespace(id=15, name="Google Chrome", total_seconds=3600,
                                  avg_activity=64.75, total_members=6, total_tasks=11)
        with patch.object(ReportsPageRepository, "usage", return_value=([app_row], 1)) as usage:
            response = ReportsPageService.apps(None, _filters(), None, "total_hours", "desc", 1, 20)
        self.assertEqual(usage.call_args[0][2], "app")
        self.assertEqual(response["items"][0]["app_id"], 15)
        self.assertEqual(response["items"][0]["app_name"], "Google Chrome")

        url_row = SimpleNamespace(id=32, name="https://github.com", total_seconds=3600,
                                  avg_activity=69.44, total_members=4, total_tasks=7)
        with patch.object(ReportsPageRepository, "usage", return_value=([url_row], 1)) as usage:
            response = ReportsPageService.urls(None, _filters(), None, "total_hours", "desc", 1, 20)
        self.assertEqual(usage.call_args[0][2], "url")
        self.assertEqual(response["items"][0]["url_id"], 32)
        self.assertEqual(response["items"][0]["url_name"], "https://github.com")


class EntryGrainSqlTests(unittest.TestCase):
    """The entry-grain subquery is the one place a fan-out bug could inflate
    every report's hours at once."""

    def setUp(self):
        self.sql = _sql(ReportsPageRepository.entry_grain_subquery(_filters()).original)

    def test_activity_is_pre_aggregated_per_time_entry_before_joining(self):
        self.assertIn("GROUP BY time_entry_activity.time_entry_id", self.sql)
        self.assertIn("LEFT OUTER JOIN (SELECT time_entry_activity.time_entry_id", self.sql)

    def test_adjustments_are_pre_aggregated_per_time_entry_before_joining(self):
        self.assertIn("GROUP BY time_entry_adjustments.time_entry_id", self.sql)

    def test_adjusted_seconds_are_floored_at_zero(self):
        self.assertIn("greatest", self.sql.lower())

    def test_approved_unmirrored_manual_entries_are_unioned_in(self):
        self.assertIn("UNION ALL", self.sql)
        self.assertIn("manual_time_entries.mirrored_time_entry_id IS NULL", self.sql)

    def test_date_window_is_applied_to_the_entry_scan(self):
        self.assertIn("time_entries.start_time >=", self.sql)
        self.assertIn("time_entries.start_time <", self.sql)

    def test_organization_scope_is_always_present(self):
        self.assertIn("time_entries.organization_id =", self.sql)
        self.assertIn("manual_time_entries.organization_id =", self.sql)

    def test_entity_filters_reach_both_branches(self):
        sql = _sql(
            ReportsPageRepository.entry_grain_subquery(
                _filters(project_id=12, task_id=101, member_id=102)
            ).original
        )
        for column in ("time_entries.project_id =", "time_entries.task_id =", "time_entries.user_id =",
                       "manual_time_entries.project_id =", "manual_time_entries.task_id =",
                       "manual_time_entries.user_id ="):
            self.assertIn(column, sql)


class GroupedQuerySqlTests(unittest.TestCase):
    """Compile the queries the four tabs actually run, through a fake Session
    that records the statements instead of executing them."""

    class _RecordingSession:
        def __init__(self):
            self.statements = []

        def execute(self, statement):
            self.statements.append(statement)
            return SimpleNamespace(all=lambda: [], one=lambda: None)

        def scalar(self, statement):
            self.statements.append(statement)
            return 0

    def _run(self, call):
        session = self._RecordingSession()
        call(session)
        return [_sql(statement) for statement in session.statements]

    def test_projects_query_groups_and_counts_distinctly(self):
        sql = self._run(lambda db: ReportsPageRepository.projects(
            db, _filters(), None, "total_hours", "desc", 1, 20
        ))[-1]
        self.assertIn("GROUP BY report_entries.project_id", sql)
        self.assertIn("count(DISTINCT report_entries.user_id)", sql)
        self.assertIn("count(DISTINCT report_entries.task_id)", sql)
        self.assertIn("JOIN projects", sql)

    def test_tasks_query_groups_by_task(self):
        sql = self._run(lambda db: ReportsPageRepository.tasks(
            db, _filters(), None, "name", "asc", 1, 20
        ))[-1]
        self.assertIn("GROUP BY report_entries.task_id", sql)
        self.assertIn("JOIN tasks", sql)

    def test_search_becomes_a_bound_ilike_not_interpolated_sql(self):
        sql = self._run(lambda db: ReportsPageRepository.projects(
            db, _filters(), "website'; DROP TABLE projects;--", "total_hours", "desc", 1, 20
        ))[-1]
        self.assertIn("ILIKE", sql.upper())
        self.assertNotIn("DROP TABLE", sql)

    def test_pagination_applies_limit_and_offset(self):
        sql = self._run(lambda db: ReportsPageRepository.projects(
            db, _filters(), None, "total_hours", "desc", 3, 20
        ))[-1]
        self.assertIn("LIMIT", sql)
        self.assertIn("OFFSET", sql)

    def test_unknown_sort_key_falls_back_to_total_seconds(self):
        sql = self._run(lambda db: ReportsPageRepository.projects(
            db, _filters(), None, "; DROP TABLE projects", "desc", 1, 20
        ))[-1]
        self.assertNotIn("DROP TABLE", sql)
        self.assertIn("ORDER BY report_rows.total_seconds DESC", sql)

    def test_sort_order_is_honoured_for_each_whitelisted_field(self):
        for field, column in (
            ("total_hours", "total_seconds"),
            ("avg_activity", "avg_activity"),
            ("total_members", "total_members"),
            ("total_tasks", "total_tasks"),
            ("name", "name"),
        ):
            sql = self._run(lambda db: ReportsPageRepository.projects(
                db, _filters(), None, field, "asc", 1, 20
            ))[-1]
            self.assertIn(f"ORDER BY report_rows.{column} ASC", sql)

    def test_app_usage_sums_usage_duration_and_joins_activity_once(self):
        sql = self._run(lambda db: ReportsPageRepository.usage(
            db, _filters(), "app", None, "total_hours", "desc", 1, 20
        ))[-1]
        self.assertIn("sum(time_entry_app_usage.duration_seconds)", sql)
        self.assertIn("min(time_entry_app_usage.id)", sql)
        self.assertIn("GROUP BY time_entry_app_usage.application_name", sql)
        self.assertIn("GROUP BY time_entry_activity.time_entry_id", sql)
        self.assertIn("JOIN time_entries", sql)

    def test_url_usage_groups_by_url_falling_back_to_domain(self):
        sql = self._run(lambda db: ReportsPageRepository.usage(
            db, _filters(), "url", None, "total_hours", "desc", 1, 20
        ))[-1]
        self.assertIn("sum(time_entry_url_usage.duration_seconds)", sql)
        self.assertIn("min(time_entry_url_usage.id)", sql)
        # url is nullable; falling back to domain keeps those rows' time visible.
        self.assertIn(
            "GROUP BY coalesce(time_entry_url_usage.url, time_entry_url_usage.domain)", sql
        )

    def test_usage_filters_apply_to_the_parent_time_entry(self):
        sql = self._run(lambda db: ReportsPageRepository.usage(
            db, _filters(project_id=12, task_id=101, member_id=102), "app", None,
            "total_hours", "desc", 1, 20,
        ))[-1]
        self.assertIn("time_entries.project_id =", sql)
        self.assertIn("time_entries.task_id =", sql)
        self.assertIn("time_entries.user_id =", sql)
        # The usage rows themselves are date-filtered too -- not just the
        # sessions they hang off.
        self.assertIn("time_entry_app_usage.recorded_at >=", sql)
        self.assertIn("time_entry_app_usage.recorded_at <", sql)

    def test_summary_aggregates_without_grouping(self):
        sql = self._run(lambda db: ReportsPageRepository.summary(db, _filters()))[-1]
        self.assertNotIn("GROUP BY report_entries", sql)
        self.assertIn("count(DISTINCT report_entries.user_id)", sql)


class RouterRegistrationTests(unittest.TestCase):
    def test_all_five_endpoints_are_mounted_under_the_react_prefix(self):
        from app.main import app

        # app.routes carries _IncludedRouter entries alongside real routes in
        # this FastAPI version, so read the paths off the generated schema.
        paths = set(app.openapi()["paths"])
        for suffix in ("summary", "projects", "tasks", "apps", "urls"):
            self.assertIn(f"/api/v1/react/reports/{suffix}", paths)

    def test_openapi_schema_builds_with_the_report_endpoints(self):
        from app.main import app

        schema = app.openapi()
        self.assertIn("/api/v1/react/reports/summary", schema["paths"])
        params = {
            param["name"]
            for param in schema["paths"]["/api/v1/react/reports/projects"]["get"]["parameters"]
        }
        self.assertLessEqual(
            {"start_date", "end_date", "project_id", "task_id", "member_id",
             "page", "limit", "sort_by", "sort_order", "search"},
            params,
        )


if __name__ == "__main__":
    unittest.main()
