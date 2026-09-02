from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.time_entry import TimeEntryStart, TimeEntryStop, TimeEntryRead
from app.services.time_entry import TimeEntryService

router = APIRouter(prefix="/time-entries", tags=["Time Entries"])

@router.post("/start", response_model=TimeEntryRead, status_code=status.HTTP_201_CREATED)
def start_timer(
    payload: TimeEntryStart,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return TimeEntryService.start_timer(
        db=db,
        project_id=payload.project_id,
        task_id=payload.task_id,
        description=payload.description,
        is_billable=payload.is_billable,
        current_user=current_user,
        started_at=payload.started_at,
    )

@router.post("/{id}/stop", response_model=TimeEntryRead)
def stop_timer(
    id: int,
    payload: TimeEntryStop,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return TimeEntryService.stop_timer(
        db=db,
        entry_id=id,
        description=payload.description,
        current_user=current_user,
        stopped_at=payload.stopped_at,
    )

@router.get("", response_model=List[TimeEntryRead])
def list_time_entries(
    project_id: Optional[int] = Query(None),
    task_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=10000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    entries, _ = TimeEntryService.list_time_entries(
        db=db,
        project_id=project_id,
        task_id=task_id,
        user_id=user_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
        current_user=current_user
    )
    return entries

@router.get("/{id}", response_model=TimeEntryRead)
def get_time_entry(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return TimeEntryService.get_time_entry(db, id, current_user)
