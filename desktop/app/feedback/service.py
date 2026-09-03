"""
Backend call for Feedback & Help.

One method, one endpoint, in the same shape as the other services in `app/`.
It carries the request and hands the answer back; it decides nothing about who
the feedback belongs to. The submitting user, their organisation and the
initial status are all determined server-side from the access token, so this
client sends only what the user actually typed.

Every failure is translated into an `ApiError` carrying a sentence that can be
shown to a person. Raw httpx errors, tracebacks and backend internals never
reach the dialog.
"""
from typing import Any, Dict

from app.api.client import ApiClient, TIMEOUT_NORMAL
from app.api.exceptions import (
    ApiConnectionError, ApiError, ApiHttpError, ApiTimeoutError, error_detail,
)
from core.logging_setup import get_logger

log = get_logger("feedback.api")

#: Mirrors the backend's MESSAGE_MAX_LENGTH. Validated here as well so an
#: over-long message is caught before a request is made, not after.
MESSAGE_MAX_LENGTH = 5000

#: The six categories the backend accepts, as wire values.
FEEDBACK_CATEGORIES = (
    "suggestion",
    "report_a_problem",
    "general_feedback",
    "need_help",
    "account_login_issue",
    "other",
)


class FeedbackApiService:
    """Client for the backend's feedback endpoint."""

    def __init__(self, api_client: ApiClient) -> None:
        self.api_client = api_client

    def submit_feedback(self, category: str, message: str) -> Dict[str, Any]:
        """Submit one feedback message and return the created record.

        Returns the backend's payload::

            {"id": int, "category": str, "message": str,
             "status": "new", "created_at": str}

        Raises `ApiError` with a user-presentable message on every failure.
        """
        text = (message or "").strip()
        if not text:
            raise ApiError("Please enter a message before submitting.")
        if len(text) > MESSAGE_MAX_LENGTH:
            raise ApiError(
                f"Your message is too long. Please keep it under "
                f"{MESSAGE_MAX_LENGTH} characters."
            )
        if category not in FEEDBACK_CATEGORIES:
            raise ApiError("Please select a category.")

        try:
            response = self.api_client.post(
                "/feedback",
                json_data={"category": category, "message": text},
                timeout=TIMEOUT_NORMAL,
            )
            return response.json()
        except ApiHttpError as exc:
            if exc.status_code in (401, 403):
                raise ApiError(
                    "Your session has expired. Please sign in again and retry.",
                    status_code=exc.status_code,
                )
            if exc.status_code == 422:
                raise ApiError(
                    error_detail(
                        exc.response_body,
                        "Please check your message and try again.",
                    ),
                    status_code=422,
                )
            log.warning("feedback submission failed: HTTP %s", exc.status_code)
            raise ApiError(
                "Something went wrong while submitting your feedback. Please try again.",
                status_code=exc.status_code,
            )
        except ApiTimeoutError:
            raise ApiError(
                "Submitting your feedback timed out. Please try again."
            )
        except ApiConnectionError:
            raise ApiError(
                "Unable to submit feedback. Please check your internet "
                "connection and try again."
            )
        except ApiError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("feedback submission failed unexpectedly", exc_info=True)
            raise ApiError(
                "Something went wrong while submitting your feedback. Please try again."
            )
