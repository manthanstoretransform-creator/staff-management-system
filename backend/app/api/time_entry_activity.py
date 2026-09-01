from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.time_entry_activity import ActivityBatchCreate, ActivityResponse
from app.schemas.time_entry_adjustment import AdjustmentCreate, AdjustmentResponse
from app.schemas.time_entry_unwanted_activity import (
    UnwantedActivityCreate, UnwantedActivityResponse,
)
from app.services.time_entry_activity import TimeEntryActivityService
from app.services.time_entry_unwanted_activity import TimeEntryUnwantedActivityService

router = APIRouter(tags=["Time Entry Activity"])


@router.post(
    "/time-entries/{time_entry_id}/activity/batch",
    status_code=status.HTTP_201_CREATED,
)
def batch_record_activity(
    time_entry_id: int,
    payload: ActivityBatchCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Batch-upload keyboard/mouse activity windows captured by the desktop
    client. Idempotent per sample via client_event_id."""
    count, records = TimeEntryActivityService.batch_record_activity(
        db=db,
        time_entry_id=time_entry_id,
        payload=payload,
        current_user=current_user,
    )
    return {
        "success": True,
        "inserted_count": count,
        "records": [ActivityResponse.model_validate(r) for r in records],
    }


@router.post(
    "/time-entries/{time_entry_id}/unwanted-activity",
    response_model=UnwantedActivityResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_unwanted_activity(
    time_entry_id: int,
    payload: UnwantedActivityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record one unwanted-activity detection event (a desktop rule's
    threshold being crossed once). Identity/context fields are derived
    server-side from the authenticated user and the time entry."""
    return TimeEntryUnwantedActivityService.record_event(
        db=db,
        time_entry_id=time_entry_id,
        payload=payload,
        current_user=current_user,
    )


@router.post(
    "/time-entries/{time_entry_id}/adjustments",
    response_model=AdjustmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_adjustment(
    time_entry_id: int,
    payload: AdjustmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a deduction against a time entry's reportable time. The
    original time_entries row is never modified; reports apply
    SUM(adjustment_seconds) on top of total_seconds."""
    return TimeEntryUnwantedActivityService.record_adjustment(
        db=db,
        time_entry_id=time_entry_id,
        payload=payload,
        current_user=current_user,
    )
