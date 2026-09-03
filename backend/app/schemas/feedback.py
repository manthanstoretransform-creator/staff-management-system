from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Upper bound on a feedback message. Long enough for a detailed bug report,
#: short enough that a single row cannot be used to store arbitrary payloads.
#: The desktop dialog enforces the same number client-side.
MESSAGE_MAX_LENGTH = 5000


class FeedbackCategory(str, Enum):
    """The six categories the Feedback & Help form offers. Nothing else is accepted."""

    suggestion = "suggestion"
    report_a_problem = "report_a_problem"
    general_feedback = "general_feedback"
    need_help = "need_help"
    account_login_issue = "account_login_issue"
    other = "other"


class FeedbackStatus(str, Enum):
    """Support workflow states. A submission always starts at ``new``."""

    new = "new"
    reviewing = "reviewing"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


class FeedbackCreate(BaseModel):
    """The only fields a client may send.

    `user_id`, `organization_id` and `status` are deliberately absent: they are
    derived server-side from the access token so a client cannot file feedback
    as another user, against another tenant, or in a non-initial state.
    """

    category: FeedbackCategory = Field(
        ...,
        description="One of the six supported feedback categories.",
        examples=["report_a_problem"],
    )
    message: str = Field(
        ...,
        max_length=MESSAGE_MAX_LENGTH,
        description="The user's message. Surrounding whitespace is trimmed; the rest is stored verbatim.",
        examples=["The timer keeps showing 00:00 after I resume from sleep."],
    )

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Message must not be empty.")
        if len(trimmed) > MESSAGE_MAX_LENGTH:
            raise ValueError(f"Message must be at most {MESSAGE_MAX_LENGTH} characters.")
        return trimmed


class FeedbackRead(BaseModel):
    """What the client gets back — enough to confirm the submission, no more."""

    id: int
    category: FeedbackCategory
    message: str
    status: FeedbackStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
