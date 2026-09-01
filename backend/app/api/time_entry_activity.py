from fastapi import APIRouter, Depends, status, Query, Path
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, date

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.time_entry_activity import (
    TimeEntryActivityCreate, TimeEntryActivityBatchCreate, TimeEntryActivityUpdate,
    TimeEntryActivityRecord, TimeEntryActivityResponse, TimeEntryActivityBatchResponse,
    TimeEntryActivityListResponse, TimeEntryActivityOverviewResponse,
    TimeEntryActivityTimelineResponse, TimeEntryActivityHourlyResponse,
    ActivityBatchCreate, ActivityResponse
)
from app.schemas.time_entry_adjustment import AdjustmentCreate, AdjustmentResponse
from app.schemas.time_entry_unwanted_activity import (
    UnwantedActivityCreate, UnwantedActivityResponse,
)
from app.services.time_entry_activity_service import TimeEntryActivityService
from app.services.time_entry_unwanted_activity import TimeEntryUnwantedActivityService

router = APIRouter(tags=["Time Entry Activity"])


@router.post(
    "/time-entry-activities",
    response_model=TimeEntryActivityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a single keyboard/mouse activity interval"
)
def create_activity(
    payload: TimeEntryActivityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    record = TimeEntryActivityService.record_activity(
        db=db,
        payload=payload,
        current_user=current_user
    )
    return {
        "success": True,
        "message": "Activity recorded successfully",
        "data": TimeEntryActivityRecord.model_validate(record)
    }


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
    "/time-entry-activities/batch",
    response_model=TimeEntryActivityBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch sync multiple desktop activity records"
)
def batch_create_activity(
    payload: TimeEntryActivityBatchCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    accepted, failed = TimeEntryActivityService.batch_record_activity(
        db=db,
        payload=payload,
        current_user=current_user
    )
    return {
        "success": True,
        "message": "Activity batch synced successfully",
        "data": {
            "accepted": accepted,
            "failed": failed
        }
    }


@router.get(
    "/time-entry-activities/overview",
    response_model=TimeEntryActivityOverviewResponse,
    summary="Get aggregated activity overview and productivity statistics"
)
def get_activity_overview(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    time_entry_id: Optional[int] = Query(None, description="Filter by time entry ID"),
    start_date: Optional[datetime] = Query(None, description="Start date/time"),
    end_date: Optional[datetime] = Query(None, description="End date/time"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    data = TimeEntryActivityService.get_overview(
        db=db,
        current_user=current_user,
        user_id=user_id,
        time_entry_id=time_entry_id,
        start_date=start_date,
        end_date=end_date
    )
    return {
        "success": True,
        "data": data
    }


@router.get(
    "/time-entry-activities/timeline",
    response_model=TimeEntryActivityTimelineResponse,
    summary="Get timeline graph points for activity percentages over time"
)
def get_activity_timeline(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    time_entry_id: Optional[int] = Query(None, description="Filter by time entry ID"),
    start_date: Optional[datetime] = Query(None, description="Start date/time"),
    end_date: Optional[datetime] = Query(None, description="End date/time"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    timeline = TimeEntryActivityService.get_timeline(
        db=db,
        current_user=current_user,
        user_id=user_id,
        time_entry_id=time_entry_id,
        start_date=start_date,
        end_date=end_date
    )
    return {
        "success": True,
        "data": timeline
    }


@router.get(
    "/time-entry-activities/hourly",
    response_model=TimeEntryActivityHourlyResponse,
    summary="Get hourly breakdown of keyboard %, mouse %, and overall activity %"
)
def get_activity_hourly(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    time_entry_id: Optional[int] = Query(None, description="Filter by time entry ID"),
    target_date: Optional[date] = Query(None, alias="date", description="Target date YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    hourly_data = TimeEntryActivityService.get_hourly(
        db=db,
        current_user=current_user,
        user_id=user_id,
        time_entry_id=time_entry_id,
        target_date=target_date
    )
    return {
        "success": True,
        "data": hourly_data
    }


@router.get(
    "/time-entry-activities",
    response_model=TimeEntryActivityListResponse,
    summary="Get filtered list of activity records with pagination"
)
def list_activities(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    time_entry_id: Optional[int] = Query(None, description="Filter by time entry ID"),
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    start_date: Optional[datetime] = Query(None, description="Start date/time"),
    end_date: Optional[datetime] = Query(None, description="End date/time"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    items, total = TimeEntryActivityService.list_activities(
        db=db,
        current_user=current_user,
        user_id=user_id,
        time_entry_id=time_entry_id,
        project_id=project_id,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit
    )
    return {
        "success": True,
        "data": {
            "items": [TimeEntryActivityRecord.model_validate(r) for r in items],
            "total": total,
            "skip": skip,
            "limit": limit
        }
    }


@router.get(
    "/time-entry-activities/{activity_id}",
    response_model=TimeEntryActivityResponse,
    summary="Get single activity record by ID"
)
def get_activity_by_id(
    activity_id: int = Path(..., gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    record = TimeEntryActivityService.get_activity_by_id(
        db=db,
        activity_id=activity_id,
        current_user=current_user
    )
    return {
        "success": True,
        "message": "Activity record retrieved successfully",
        "data": TimeEntryActivityRecord.model_validate(record)
    }


@router.patch(
    "/time-entry-activities/{activity_id}",
    response_model=TimeEntryActivityResponse,
    summary="Update activity record by ID"
)
def update_activity(
    payload: TimeEntryActivityUpdate,
    activity_id: int = Path(..., gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    record = TimeEntryActivityService.update_activity(
        db=db,
        activity_id=activity_id,
        payload=payload,
        current_user=current_user
    )
    return {
        "success": True,
        "message": "Activity record updated successfully",
        "data": TimeEntryActivityRecord.model_validate(record)
    }


@router.delete(
    "/time-entry-activities/{activity_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete activity record by ID"
)
def delete_activity(
    activity_id: int = Path(..., gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    TimeEntryActivityService.delete_activity(
        db=db,
        activity_id=activity_id,
        current_user=current_user
    )
    return {
        "success": True,
        "message": f"Activity record {activity_id} deleted successfully"
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
