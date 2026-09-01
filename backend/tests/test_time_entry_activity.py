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
from app.services.time_entry_activity import TimeEntryActivityService
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
