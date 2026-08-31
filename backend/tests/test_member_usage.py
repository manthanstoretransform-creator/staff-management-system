import unittest
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.services.member_usage import MemberUsageService


def _row(**kwargs):
    return SimpleNamespace(**kwargs)


class DateRangeValidationTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=54, organization_id=1)

    def test_no_date_filter_at_all_raises_400(self):
        with self.assertRaises(HTTPException) as error:
            MemberUsageService.build_details(None, self.user, 10, None, None, None)
        self.assertEqual(error.exception.status_code, 400)

    def test_date_and_range_together_raises_400(self):
        with self.assertRaises(HTTPException) as error:
            MemberUsageService.build_details(None, self.user, 10, date(2026, 8, 1), date(2026, 8, 1), date(2026, 8, 5))
        self.assertEqual(error.exception.status_code, 400)

    def test_start_date_without_end_date_raises_400(self):
        with self.assertRaises(HTTPException) as error:
            MemberUsageService.build_details(None, self.user, 10, None, date(2026, 8, 1), None)
        self.assertEqual(error.exception.status_code, 400)

    def test_start_date_after_end_date_raises_400(self):
        with self.assertRaises(HTTPException) as error:
            MemberUsageService.build_details(None, self.user, 10, None, date(2026, 8, 27), date(2026, 8, 1))
        self.assertEqual(error.exception.status_code, 400)

    def test_range_over_31_days_raises_400(self):
        with self.assertRaises(HTTPException) as error:
            MemberUsageService.build_details(None, self.user, 10, None, date(2026, 7, 1), date(2026, 8, 15))
        self.assertEqual(error.exception.status_code, 400)

    def test_range_of_exactly_31_days_is_allowed(self):
        member = SimpleNamespace(
            id=10, name="Ada", email="ada@example.com", role_name="employee", status="active",
            designation=None, date_of_joining=None, date_of_birth=None,
            created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1), organization_id=1,
        )
        with patch("app.services.member_usage.MemberService.get", return_value=member), \
             patch("app.services.member_usage.MemberRepository.organization_name", return_value="Acme"), \
             patch("app.services.member_usage.MemberUsageRepository.daily_activity", return_value=[]), \
             patch("app.services.member_usage.MemberUsageRepository.daily_app_usage", return_value=[]), \
             patch("app.services.member_usage.MemberUsageRepository.daily_url_usage", return_value=[]):
            response = MemberUsageService.build_details(None, self.user, 10, None, date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(response["start_date"], date(2026, 7, 1))


class MemberDetailsTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=54, organization_id=1)
        self.member = SimpleNamespace(
            id=10, name="Ada Lovelace", email="ada@example.com", role_name="employee", status="active",
            designation="Engineer", date_of_joining=date(2025, 1, 1), date_of_birth=date(1990, 1, 1),
            created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 2), organization_id=1,
        )

    def test_member_payload_includes_organization(self):
        with patch("app.services.member_usage.MemberService.get", return_value=self.member), \
             patch("app.services.member_usage.MemberRepository.organization_name", return_value="Acme Org"), \
             patch("app.services.member_usage.MemberUsageRepository.daily_activity", return_value=[]), \
             patch("app.services.member_usage.MemberUsageRepository.daily_app_usage", return_value=[]), \
             patch("app.services.member_usage.MemberUsageRepository.daily_url_usage", return_value=[]):
            response = MemberUsageService.build_details(None, self.user, 10, date(2026, 8, 31), None, None)
        self.assertEqual(response["member"]["organization"], {"id": 1, "name": "Acme Org"})
        self.assertEqual(response["member"]["email"], "ada@example.com")

    def test_daily_activity_rounds_to_whole_percentage(self):
        rows = [_row(day=date(2026, 8, 31), keyboard_strokes=1250, mouse_clicks=340, mouse_movements=890, activity_percentage=71.6)]
        with patch("app.services.member_usage.MemberService.get", return_value=self.member), \
             patch("app.services.member_usage.MemberRepository.organization_name", return_value="Acme"), \
             patch("app.services.member_usage.MemberUsageRepository.daily_activity", return_value=rows), \
             patch("app.services.member_usage.MemberUsageRepository.daily_app_usage", return_value=[]), \
             patch("app.services.member_usage.MemberUsageRepository.daily_url_usage", return_value=[]):
            response = MemberUsageService.build_details(None, self.user, 10, date(2026, 8, 31), None, None)
        item = response["daily_activity"][0]
        self.assertEqual(item["activity_percentage"], 72)
        self.assertEqual(item["keyboard_strokes"], 1250)

    def test_app_usage_percentage_matches_spec_example(self):
        rows = [
            _row(day=date(2026, 8, 31), application_name="Google Chrome", duration_seconds=7200),
            _row(day=date(2026, 8, 31), application_name="Visual Studio Code", duration_seconds=3600),
            _row(day=date(2026, 8, 31), application_name="Slack", duration_seconds=1200),
        ]
        with patch("app.services.member_usage.MemberService.get", return_value=self.member), \
             patch("app.services.member_usage.MemberRepository.organization_name", return_value="Acme"), \
             patch("app.services.member_usage.MemberUsageRepository.daily_activity", return_value=[]), \
             patch("app.services.member_usage.MemberUsageRepository.daily_app_usage", return_value=rows), \
             patch("app.services.member_usage.MemberUsageRepository.daily_url_usage", return_value=[]):
            response = MemberUsageService.build_details(None, self.user, 10, date(2026, 8, 31), None, None)
        day = response["application_usage"][0]
        self.assertEqual(day["date"], date(2026, 8, 31))
        percentages = [app["usage_percentage"] for app in day["applications"]]
        self.assertEqual(percentages, [60, 30, 10])
        self.assertEqual(day["applications"][0]["duration"], "2h 0m")

    def test_url_usage_kept_per_url_not_aggregated_by_domain(self):
        rows = [
            _row(day=date(2026, 8, 31), browser_name="Chrome", domain="github.com", url="https://github.com/a", page_title="Repo A", duration_seconds=3600),
            _row(day=date(2026, 8, 31), browser_name="Chrome", domain="github.com", url="https://github.com/b", page_title="Repo B", duration_seconds=1800),
        ]
        with patch("app.services.member_usage.MemberService.get", return_value=self.member), \
             patch("app.services.member_usage.MemberRepository.organization_name", return_value="Acme"), \
             patch("app.services.member_usage.MemberUsageRepository.daily_activity", return_value=[]), \
             patch("app.services.member_usage.MemberUsageRepository.daily_app_usage", return_value=[]), \
             patch("app.services.member_usage.MemberUsageRepository.daily_url_usage", return_value=rows):
            response = MemberUsageService.build_details(None, self.user, 10, date(2026, 8, 31), None, None)
        urls = response["url_usage"][0]["urls"]
        self.assertEqual(len(urls), 2)
        self.assertEqual({item["url"] for item in urls}, {"https://github.com/a", "https://github.com/b"})

    def test_no_usage_returns_empty_lists_not_error(self):
        with patch("app.services.member_usage.MemberService.get", return_value=self.member), \
             patch("app.services.member_usage.MemberRepository.organization_name", return_value="Acme"), \
             patch("app.services.member_usage.MemberUsageRepository.daily_activity", return_value=[]), \
             patch("app.services.member_usage.MemberUsageRepository.daily_app_usage", return_value=[]), \
             patch("app.services.member_usage.MemberUsageRepository.daily_url_usage", return_value=[]):
            response = MemberUsageService.build_details(None, self.user, 10, date(2026, 8, 31), None, None)
        self.assertEqual(response["daily_activity"], [])
        self.assertEqual(response["application_usage"], [])
        self.assertEqual(response["url_usage"], [])


if __name__ == "__main__":
    unittest.main()
