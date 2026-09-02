import pytest
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from fastapi import HTTPException
from pydantic import ValidationError

from app.services.time_entry_activity_service import calculate_activity_percentage
from app.schemas.time_entry_activity import TimeEntryActivityCreate, TimeEntryActivityBatchCreate
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.schemas.time_entry_activity import ActivityBatchCreate, ActivitySampleCreate
from app.schemas.time_entry_adjustment import AdjustmentCreate
from app.schemas.time_entry_unwanted_activity import UnwantedActivityCreate
from app.services.time_entry_activity import (
    TimeEntryActivityService, weighted_activity_percentage,
)
from app.services.time_entry_unwanted_activity import TimeEntryUnwantedActivityService


def test_activity_percentage_calculation():
    # 0 activity = 0%
    assert calculate_activity_percentage(0, 0, 0) == 0

    # Half activity
    assert calculate_activity_percentage(60, 15, 200) == 50

    # Max / overload activity caps at 100%
    assert calculate_activity_percentage(300, 100, 1000) == 100

    # Low activity
    assert calculate_activity_percentage(12, 3, 40) == 10


def test_activity_schema_validation():
    # Valid payload
    payload = TimeEntryActivityCreate(
        organization_id=1,
        time_entry_id=10,
        keyboard_strokes=50,
        mouse_clicks=10,
        mouse_movements=100,
        activity_percentage=75
    )
    assert payload.activity_percentage == 75

    # Batch payload
    batch = TimeEntryActivityBatchCreate(activities=[payload])
    assert len(batch.activities) == 1


def _user() -> User:
    return User(id=1, organization_id=10, permissions={})


def _entry(**overrides) -> TimeEntry:
    defaults = dict(
        id=100, organization_id=10, user_id=1, project_id=5, task_id=7,
        status="running", end_time=None,
    )
    defaults.update(overrides)
    return TimeEntry(**defaults)


def _sample(**overrides) -> ActivitySampleCreate:
    defaults = dict(
        recorded_at=datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc),
        keyboard_strokes=120, mouse_clicks=30, mouse_movements=900,
        activity_percentage=85, client_event_id="evt-1",
    )
    defaults.update(overrides)
    return ActivitySampleCreate(**defaults)


class TestActivityBatch(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()

    @patch("app.services.time_entry_activity.TimeEntryActivityRepository.create_batch")
    @patch("app.services.time_entry_activity.TimeEntryRepository.get_by_id")
    def test_batch_success(self, mock_get, mock_create):
        mock_get.return_value = _entry()
        mock_create.return_value = [MagicMock()]

        payload = ActivityBatchCreate(samples=[_sample()])
        count, _ = TimeEntryActivityService.batch_record_activity(self.db, 100, payload, _user())

        self.assertEqual(count, 1)
        mock_create.assert_called_once_with(
            db=self.db, organization_id=10, time_entry_id=100, samples=payload.samples,
        )

    @patch("app.services.time_entry_activity.TimeEntryRepository.get_by_id")
    def test_batch_rejects_other_users_entry(self, mock_get):
        mock_get.return_value = _entry(user_id=99)
        with self.assertRaises(HTTPException) as ctx:
            TimeEntryActivityService.batch_record_activity(
                self.db, 100, ActivityBatchCreate(samples=[_sample()]), _user()
            )
        self.assertEqual(ctx.exception.status_code, 403)

    @patch("app.services.time_entry_activity.TimeEntryRepository.get_by_id")
    def test_batch_rejects_other_orgs_entry_as_not_found(self, mock_get):
        mock_get.return_value = _entry(organization_id=99)
        with self.assertRaises(HTTPException) as ctx:
            TimeEntryActivityService.batch_record_activity(
                self.db, 100, ActivityBatchCreate(samples=[_sample()]), _user()
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_batch_rejects_empty(self):
        with self.assertRaises(HTTPException) as ctx:
            TimeEntryActivityService.batch_record_activity(
                self.db, 100, ActivityBatchCreate(samples=[]), _user()
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_sample_schema_enforces_percentage_bounds(self):
        with self.assertRaises(ValidationError):
            _sample(activity_percentage=101)
        with self.assertRaises(ValidationError):
            _sample(activity_percentage=-1)


class TestUnwantedActivity(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()

    @patch("app.services.time_entry_unwanted_activity.TimeEntryUnwantedActivityRepository")
    @patch("app.services.time_entry_unwanted_activity.TimeEntryRepository.get_by_id")
    def test_event_identity_comes_from_the_entry_not_the_client(self, mock_get, mock_repo):
        mock_get.return_value = _entry()
        mock_repo.get_by_client_event_id.return_value = None

        payload = UnwantedActivityCreate(
            activity_type="repeated_key", key_or_action="ctrl",
            occurrence_count=15, alerted=True, alert_count=1, client_event_id="ua-1",
        )
        TimeEntryUnwantedActivityService.record_event(self.db, 100, payload, _user())

        kwargs = mock_repo.create.call_args.kwargs
        self.assertEqual(kwargs["organization_id"], 10)
        self.assertEqual(kwargs["user_id"], 1)
        self.assertEqual(kwargs["project_id"], 5)
        self.assertEqual(kwargs["task_id"], 7)
        self.assertEqual(kwargs["key_or_action"], "ctrl")
        self.assertEqual(kwargs["occurrence_count"], 15)

    @patch("app.services.time_entry_unwanted_activity.TimeEntryUnwantedActivityRepository")
    @patch("app.services.time_entry_unwanted_activity.TimeEntryRepository.get_by_id")
    def test_event_retry_is_idempotent(self, mock_get, mock_repo):
        mock_get.return_value = _entry()
        existing = MagicMock()
        mock_repo.get_by_client_event_id.return_value = existing

        payload = UnwantedActivityCreate(
            activity_type="repeated_key", key_or_action="ctrl",
            occurrence_count=15, client_event_id="ua-1",
        )
        result = TimeEntryUnwantedActivityService.record_event(self.db, 100, payload, _user())

        self.assertIs(result, existing)
        mock_repo.create.assert_not_called()


class TestAdjustments(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()

    def test_schema_rejects_positive_and_oversized_adjustments(self):
        with self.assertRaises(ValidationError):
            AdjustmentCreate(adjustment_seconds=600, reason="credit")
        with self.assertRaises(ValidationError):
            AdjustmentCreate(adjustment_seconds=0, reason="zero")
        with self.assertRaises(ValidationError):
            AdjustmentCreate(adjustment_seconds=-4000, reason="too big")

    @patch("app.services.time_entry_unwanted_activity.TimeEntryAdjustmentRepository")
    @patch("app.services.time_entry_unwanted_activity.TimeEntryUnwantedActivityRepository")
    @patch("app.services.time_entry_unwanted_activity.TimeEntryRepository.get_by_id")
    def test_adjustment_links_source_event_and_derives_identity(
        self, mock_get, mock_ua_repo, mock_adj_repo
    ):
        mock_get.return_value = _entry()
        mock_adj_repo.get_by_client_event_id.return_value = None
        source = MagicMock(id=55, time_entry_id=100)
        mock_ua_repo.get_by_client_event_id.return_value = source

        payload = AdjustmentCreate(
            adjustment_seconds=-600, reason="3 unwanted-activity occurrences",
            source_activity_type="repeated_key", source_key_or_action="ctrl",
            source_client_event_id="ua-1", client_event_id="adj-1",
        )
        TimeEntryUnwantedActivityService.record_adjustment(self.db, 100, payload, _user())

        kwargs = mock_adj_repo.create.call_args.kwargs
        self.assertEqual(kwargs["adjustment_seconds"], -600)
        self.assertEqual(kwargs["unwanted_activity_id"], 55)
        self.assertEqual(kwargs["organization_id"], 10)
        self.assertEqual(kwargs["user_id"], 1)

    @patch("app.services.time_entry_unwanted_activity.TimeEntryAdjustmentRepository")
    @patch("app.services.time_entry_unwanted_activity.TimeEntryRepository.get_by_id")
    def test_adjustment_retry_is_idempotent_never_deducting_twice(self, mock_get, mock_adj_repo):
        mock_get.return_value = _entry()
        existing = MagicMock()
        mock_adj_repo.get_by_client_event_id.return_value = existing

        payload = AdjustmentCreate(
            adjustment_seconds=-600, reason="dup retry", client_event_id="adj-1",
        )
        result = TimeEntryUnwantedActivityService.record_adjustment(self.db, 100, payload, _user())

        self.assertIs(result, existing)
        mock_adj_repo.create.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class TestBatchRouteWiring(unittest.TestCase):
    """The route must reach the service that actually implements this flow.

    Two services carry a `batch_record_activity`: the per-entry one used
    here, and the legacy `/time-entry-activities/batch` one, whose signature
    takes no time_entry_id and reads `payload.activities` where this payload
    has `samples`. The route imported the legacy service, so every desktop
    upload raised a TypeError and came back as HTTP 500 -- and because 500
    is not 404, the client's fallback to the legacy endpoint never engaged
    either. The service itself was well covered; nothing checked that the
    route called it.
    """

    def test_per_entry_route_dispatches_to_the_per_entry_service(self):
        from app.api import time_entry_activity as route_module

        payload = ActivityBatchCreate(samples=[_sample()])
        db = MagicMock()
        user = _user()
        record = MagicMock()

        with patch.object(
            route_module.EntryActivityService, "batch_record_activity",
            return_value=(1, [record]),
        ) as service, patch.object(
            route_module.ActivityResponse, "model_validate", return_value={"id": 1},
        ):
            response = route_module.batch_record_activity(
                time_entry_id=100, payload=payload, current_user=user, db=db,
            )

        service.assert_called_once_with(
            db=db, time_entry_id=100, payload=payload, current_user=user,
        )
        self.assertTrue(response["success"])
        self.assertEqual(response["inserted_count"], 1)

    def test_the_route_and_its_service_agree_on_the_signature(self):
        """A direct guard against the mismatch: the bound service must
        accept exactly the keyword arguments the route passes."""
        import inspect
        from app.api import time_entry_activity as route_module

        signature = inspect.signature(
            route_module.EntryActivityService.batch_record_activity
        )
        signature.bind(
            db=MagicMock(),
            time_entry_id=100,
            payload=ActivityBatchCreate(samples=[_sample()]),
            current_user=_user(),
        )


# ── Today's activity summary ─────────────────────────────────────────────────
#
# The card this powers shows a single percentage, so the two failure modes
# that matter are the arithmetic (a mean of percentages instead of a
# duration-weighted one) and the day boundary (UTC midnight instead of IST).


def test_the_weighting_is_by_duration_not_a_mean_of_percentages():
    """10 minutes at 90% and an hour at 20% is 30%, not the 55% a plain
    average of the two percentages would give."""
    weighted = 90 * 600 + 20 * 3600
    assert round(weighted_activity_percentage(weighted, 600 + 3600)) == 30


def test_an_unmeasured_day_is_zero_rather_than_a_division_by_zero():
    assert weighted_activity_percentage(0, 0) == 0.0
    assert weighted_activity_percentage(500, 0) == 0.0
    assert weighted_activity_percentage(500, -10) == 0.0


def test_the_weighted_percentage_is_clamped_to_the_valid_range():
    assert weighted_activity_percentage(100 * 60 * 2, 60) == 100.0
    assert weighted_activity_percentage(-500, 60) == 0.0


class TestTodaySummary(unittest.TestCase):
    """The summary is scoped to the caller and to their IST calendar day."""

    def setUp(self):
        self.db = MagicMock()
        self.user = _user()

    def _run(self, totals=(90 * 600 + 20 * 3600, 4200), tracked=4200, running=None,
             target_date=None):
        with patch(
            "app.services.time_entry_activity.TimeEntryActivityRepository.get_day_totals",
            return_value=totals,
        ) as day_totals, patch(
            "app.services.time_entry_activity.TimeEntryRepository.get_day_tracked_seconds",
            return_value=tracked,
        ), patch(
            "app.services.time_entry_activity.TimeEntryRepository.get_active_for_user",
            return_value=running,
        ):
            summary = TimeEntryActivityService.get_today_summary(
                db=self.db, current_user=self.user, target_date=target_date
            )
        return summary, day_totals

    def test_it_returns_the_duration_weighted_percentage(self):
        summary, _ = self._run()
        self.assertEqual(summary.activity_percentage, 30)
        self.assertEqual(summary.measured_seconds, 4200)
        self.assertEqual(summary.tracked_seconds, 4200)
        self.assertFalse(summary.is_tracking)

    def test_a_day_with_no_windows_reports_zero_not_an_error(self):
        summary, _ = self._run(totals=(0, 0), tracked=0)
        self.assertEqual(summary.activity_percentage, 0)
        self.assertEqual(summary.activity_percentage_exact, 0.0)
        self.assertEqual(summary.measured_seconds, 0)

    def test_a_running_entry_is_reported_as_tracking(self):
        summary, _ = self._run(running=_entry())
        self.assertTrue(summary.is_tracking)

    def test_the_range_is_the_ist_calendar_day_not_the_utc_one(self):
        from datetime import date, timezone as tz

        summary, day_totals = self._run(target_date=date(2026, 9, 2))
        kwargs = day_totals.call_args.kwargs

        self.assertEqual(summary.date, "2026-09-02")
        # 00:00 IST is 18:30 UTC on the previous day.
        self.assertEqual(
            kwargs["start_utc"].astimezone(tz.utc),
            datetime(2026, 9, 1, 18, 30, tzinfo=tz.utc),
        )
        self.assertEqual(
            (kwargs["end_utc"] - kwargs["start_utc"]).total_seconds(), 86400
        )

    def test_it_is_scoped_to_the_authenticated_user_and_organisation(self):
        """There is no user_id parameter, so the summary cannot be pointed at
        someone else's day."""
        _, day_totals = self._run()
        kwargs = day_totals.call_args.kwargs
        self.assertEqual(kwargs["user_id"], self.user.id)
        self.assertEqual(kwargs["organization_id"], self.user.organization_id)


def test_the_upload_schema_carries_the_windows_measured_length():
    """The desktop's tail window is shorter than a minute; without this the
    backend would weight it as a full one."""
    assert _sample().window_seconds == 60
    assert _sample(window_seconds=12).window_seconds == 12
