"""
Coverage for the date-scoped URL usage summary and the midnight merge rule.

Two behaviours the desktop's per-day Activity panel depends on:

  * `GET /url-usage/summary` reports a **complete** window. The desktop used to
    build its totals from `GET /url-usage`, a raw listing behind `limit=100`,
    so a busy day silently showed a partial total and called it the day's
    usage. Aggregation belongs in the database.
  * Consecutive identical URL sessions are merged into one row, and merging
    advances that row's `recorded_at`. Across midnight that moves the whole
    duration onto the later day, so the merge must stop at the day boundary.

Scoping is checked here too: the date filter must never become a way to read
another user's browsing.
"""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.core.time_format import IST, ist_day_start_utc
from app.models.time_entry import TimeEntry
from app.models.time_entry_url_usage import TimeEntryUrlUsage
from app.models.user import User
from app.schemas.url_usage import URLUsageCreate
from app.services.url_usage_service import URLUsageService, same_ist_day


def _ist_moment(year, month, day, hour, minute) -> datetime:
    """An IST wall clock as the UTC instant the column stores."""
    return datetime(year, month, day, hour, minute, tzinfo=IST).astimezone(timezone.utc)


class SameIstDayTests(unittest.TestCase):
    def test_two_instants_in_one_ist_day_match(self):
        self.assertTrue(
            same_ist_day(_ist_moment(2026, 9, 8, 9, 0), _ist_moment(2026, 9, 8, 23, 59))
        )

    def test_instants_either_side_of_midnight_do_not_match(self):
        """One minute apart, and on different days. That is the point."""
        self.assertFalse(
            same_ist_day(_ist_moment(2026, 9, 8, 23, 59), _ist_moment(2026, 9, 9, 0, 0))
        )

    def test_the_boundary_is_ist_not_utc(self):
        """18:00 and 19:00 UTC straddle IST midnight (05:30 offset), so they
        are different IST days despite being the same UTC day."""
        a = datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc)
        b = datetime(2026, 9, 8, 19, 0, tzinfo=timezone.utc)
        self.assertFalse(same_ist_day(a, b))


class MidnightMergeTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.user = User(id=1, organization_id=10, permissions={})
        self.entry = TimeEntry(
            id=100, organization_id=10, user_id=1, status="running", end_time=None
        )

    def _payload(self, recorded_at):
        return URLUsageCreate(
            time_entry_id=100,
            browser_name="Google Chrome",
            domain="github.com",
            url="https://github.com/org/repo",
            page_title="GitHub",
            duration_seconds=40,
            recorded_at=recorded_at,
        )

    def _latest(self, recorded_at):
        return TimeEntryUrlUsage(
            id=1, organization_id=10, time_entry_id=100,
            browser_name="Google Chrome", domain="github.com",
            url="https://github.com/org/repo", page_title="GitHub",
            duration_seconds=20, recorded_at=recorded_at,
        )

    @patch("app.repositories.time_entry.TimeEntryRepository.get_by_id")
    @patch("app.repositories.url_usage_repository.URLUsageRepository.get_by_client_event_id")
    @patch("app.repositories.url_usage_repository.URLUsageRepository.get_latest_record")
    @patch("app.repositories.url_usage_repository.URLUsageRepository.update_duration_and_time")
    @patch("app.repositories.url_usage_repository.URLUsageRepository.create")
    def test_the_same_page_within_the_window_and_day_still_merges(
        self, mock_create, mock_update, mock_latest, mock_event_id, mock_entry
    ):
        mock_entry.return_value = self.entry
        mock_event_id.return_value = None
        mock_latest.return_value = self._latest(_ist_moment(2026, 9, 8, 14, 0))

        URLUsageService.record_usage(
            self.db, self._payload(_ist_moment(2026, 9, 8, 14, 1)), self.user
        )

        mock_update.assert_called_once()
        mock_create.assert_not_called()

    @patch("app.repositories.time_entry.TimeEntryRepository.get_by_id")
    @patch("app.repositories.url_usage_repository.URLUsageRepository.get_by_client_event_id")
    @patch("app.repositories.url_usage_repository.URLUsageRepository.get_latest_record")
    @patch("app.repositories.url_usage_repository.URLUsageRepository.update_duration_and_time")
    @patch("app.repositories.url_usage_repository.URLUsageRepository.create")
    def test_the_same_page_across_midnight_becomes_a_second_row(
        self, mock_create, mock_update, mock_latest, mock_event_id, mock_entry
    ):
        """Within the five-minute window, same browser, same URL -- and still
        not merged, because merging would credit both minutes to whichever day
        the merged row ended up dated."""
        mock_entry.return_value = self.entry
        mock_event_id.return_value = None
        mock_latest.return_value = self._latest(_ist_moment(2026, 9, 8, 23, 59))

        URLUsageService.record_usage(
            self.db, self._payload(_ist_moment(2026, 9, 9, 0, 0)), self.user
        )

        mock_update.assert_not_called()
        mock_create.assert_called_once()


class PageSummaryScopingTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.member = User(id=1, organization_id=10, permissions={"time_entries:view_all": False})
        self.admin = User(id=2, organization_id=10, permissions={"time_entries:view_all": True})

    @patch("app.repositories.url_usage_repository.URLUsageRepository.get_page_summary")
    def test_a_member_is_pinned_to_their_own_records(self, mock_summary):
        """The date filter must not become a way to read someone else's
        browsing: an explicit user_id from an unprivileged caller is ignored."""
        mock_summary.return_value = []

        URLUsageService.get_page_summary_global(
            db=self.db, user_id=999, start_date=None, end_date=None,
            current_user=self.member,
        )

        self.assertEqual(mock_summary.call_args.kwargs["user_id"], self.member.id)

    @patch("app.repositories.url_usage_repository.URLUsageRepository.get_page_summary")
    def test_a_privileged_caller_may_ask_for_another_user(self, mock_summary):
        mock_summary.return_value = []

        URLUsageService.get_page_summary_global(
            db=self.db, user_id=7, start_date=None, end_date=None,
            current_user=self.admin,
        )

        self.assertEqual(mock_summary.call_args.kwargs["user_id"], 7)

    @patch("app.repositories.url_usage_repository.URLUsageRepository.get_page_summary")
    def test_the_organization_is_always_the_callers_own(self, mock_summary):
        mock_summary.return_value = []

        URLUsageService.get_page_summary_global(
            db=self.db, user_id=None, start_date=None, end_date=None,
            current_user=self.member,
        )

        self.assertEqual(mock_summary.call_args.kwargs["organization_id"], 10)

    @patch("app.repositories.url_usage_repository.URLUsageRepository.get_page_summary")
    def test_the_day_window_is_passed_through_unchanged(self, mock_summary):
        mock_summary.return_value = []
        start = ist_day_start_utc(datetime(2026, 9, 8).date())
        end = start + timedelta(days=1)

        URLUsageService.get_page_summary_global(
            db=self.db, user_id=None, start_date=start, end_date=end,
            current_user=self.member,
        )

        self.assertEqual(mock_summary.call_args.kwargs["start_time"], start)
        self.assertEqual(mock_summary.call_args.kwargs["end_time"], end)

    @patch("app.repositories.url_usage_repository.URLUsageRepository.get_page_summary")
    def test_the_total_is_the_sum_of_every_page_not_a_capped_page_of_rows(
        self, mock_summary
    ):
        mock_summary.return_value = [
            ("github.com", "https://github.com/a", "A", 300),
            ("github.com", "https://github.com/b", "B", 120),
            ("news.example", None, None, 45),
        ]

        data = URLUsageService.get_page_summary_global(
            db=self.db, user_id=None, start_date=None, end_date=None,
            current_user=self.member,
        )

        self.assertEqual(data["total_duration_seconds"], 465)
        self.assertEqual(len(data["pages"]), 3)
        self.assertEqual(data["pages"][0]["url"], "https://github.com/a")
        self.assertIsNone(data["pages"][2]["url"])


if __name__ == "__main__":
    unittest.main()
