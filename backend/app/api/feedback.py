from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.feedback import FeedbackCreate, FeedbackRead
from app.services.feedback import FeedbackService

router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.post(
    "",
    response_model=FeedbackRead,
    summary="Submit a Feedback & Help message.",
    description=(
        "Records feedback from the authenticated user. The submitting user and "
        "their organization are taken from the access token, and the status is "
        "always set to 'new' — none of the three can be supplied by the client."
    ),
    responses={422: {"description": "Unsupported category, or an empty/too-long message."}},
)
def submit_feedback(
    feedback_in: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return FeedbackService.submit_feedback(db, feedback_in, current_user)
