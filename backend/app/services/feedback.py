from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.feedback_request import FeedbackRequest
from app.models.user import User
from app.repositories.feedback import FeedbackRepository
from app.schemas.feedback import FeedbackCreate, FeedbackStatus


class FeedbackService:
    """Business rules for Feedback & Help submissions.

    The one rule that matters: identity and tenancy come from the authenticated
    user, never from the request body, and a new submission is always ``new``.
    """

    @staticmethod
    def submit_feedback(
        db: Session, feedback_in: FeedbackCreate, current_user: User
    ) -> FeedbackRequest:
        # The schema already trims and rejects a blank message; this guards the
        # service against a caller that builds the model some other way.
        message = feedback_in.message.strip()
        if not message:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Message must not be empty.",
            )

        if not current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is not associated with an organization.",
            )

        return FeedbackRepository.create(
            db=db,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            category=feedback_in.category.value,
            message=message,
            status=FeedbackStatus.new.value,
        )
