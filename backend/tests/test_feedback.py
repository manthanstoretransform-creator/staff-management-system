"""Feedback & Help — the rules that must hold for a submission.

The point of these tests is the trust boundary: a client sends a category and
a message and nothing else, and the record that lands carries the *server's*
idea of who the user is, which organization they belong to, and what state a
new submission starts in.
"""
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.models.user import User
from app.schemas.feedback import (
    MESSAGE_MAX_LENGTH, FeedbackCategory, FeedbackCreate, FeedbackStatus,
)
from app.services.feedback import FeedbackService

SVC = "app.services.feedback"


def _user(user_id=42, organization_id=7):
    return User(id=user_id, organization_id=organization_id, role_name="employee", permissions={})


class TestFeedbackSchemaValidation(unittest.TestCase):
    def test_a_whitespace_only_message_is_rejected(self):
        with self.assertRaises(ValidationError):
            FeedbackCreate(category="suggestion", message="   \n\t  ")

    def test_an_empty_message_is_rejected(self):
        with self.assertRaises(ValidationError):
            FeedbackCreate(category="suggestion", message="")

    def test_a_message_longer_than_the_maximum_is_rejected(self):
        with self.assertRaises(ValidationError):
            FeedbackCreate(category="other", message="x" * (MESSAGE_MAX_LENGTH + 1))

    def test_an_unsupported_category_is_rejected(self):
        with self.assertRaises(ValidationError):
            FeedbackCreate(category="please_delete_my_data", message="hello")

    def test_the_six_supported_categories_are_exactly_these(self):
        self.assertEqual(
            [c.value for c in FeedbackCategory],
            [
                "suggestion",
                "report_a_problem",
                "general_feedback",
                "need_help",
                "account_login_issue",
                "other",
            ],
        )

    def test_surrounding_whitespace_is_trimmed_but_the_text_is_not_otherwise_altered(self):
        payload = FeedbackCreate(
            category="need_help", message="  the timer  shows 00:00\nafter sleep  "
        )
        self.assertEqual(payload.message, "the timer  shows 00:00\nafter sleep")

    def test_a_client_cannot_supply_a_status_a_user_id_or_an_organization_id(self):
        payload = FeedbackCreate.model_validate({
            "category": "other",
            "message": "hi",
            "status": "resolved",
            "user_id": 999,
            "organization_id": 999,
        })
        self.assertEqual(set(payload.model_dump().keys()), {"category", "message"})


class TestFeedbackService(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.payload = FeedbackCreate(
            category="report_a_problem", message="  The timer resets on resume.  "
        )

    def test_the_record_takes_its_identity_and_tenancy_from_the_authenticated_user(self):
        with patch(f"{SVC}.FeedbackRepository") as repo:
            FeedbackService.submit_feedback(self.db, self.payload, _user(user_id=42, organization_id=7))

        kwargs = repo.create.call_args.kwargs
        self.assertEqual(kwargs["user_id"], 42)
        self.assertEqual(kwargs["organization_id"], 7)

    def test_a_new_submission_always_starts_at_new(self):
        with patch(f"{SVC}.FeedbackRepository") as repo:
            FeedbackService.submit_feedback(self.db, self.payload, _user())

        self.assertEqual(repo.create.call_args.kwargs["status"], FeedbackStatus.new.value)

    def test_the_category_is_stored_as_its_wire_value_and_the_message_trimmed(self):
        with patch(f"{SVC}.FeedbackRepository") as repo:
            FeedbackService.submit_feedback(self.db, self.payload, _user())

        kwargs = repo.create.call_args.kwargs
        self.assertEqual(kwargs["category"], "report_a_problem")
        self.assertEqual(kwargs["message"], "The timer resets on resume.")

    def test_a_user_without_an_organization_cannot_submit_feedback(self):
        user = _user()
        user.organization_id = None
        with patch(f"{SVC}.FeedbackRepository") as repo:
            with self.assertRaises(HTTPException) as ctx:
                FeedbackService.submit_feedback(self.db, self.payload, user)

        self.assertEqual(ctx.exception.status_code, 403)
        repo.create.assert_not_called()

    def test_a_message_that_is_blank_after_trimming_never_reaches_the_repository(self):
        # The schema normally stops this; the service guards the path anyway.
        payload = FeedbackCreate.model_construct(
            category=FeedbackCategory.other, message="   "
        )
        with patch(f"{SVC}.FeedbackRepository") as repo:
            with self.assertRaises(HTTPException) as ctx:
                FeedbackService.submit_feedback(self.db, payload, _user())

        self.assertEqual(ctx.exception.status_code, 422)
        repo.create.assert_not_called()
