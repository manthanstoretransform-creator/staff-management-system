from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.time_entry_screenshot import TimeEntryScreenshotCreate, TimeEntryScreenshotRead
from app.services.time_entry_screenshot import TimeEntryScreenshotService

router = APIRouter(prefix="/time-entry-screenshots", tags=["Time Entry Screenshots"])

@router.post("", response_model=TimeEntryScreenshotRead, status_code=status.HTTP_201_CREATED)
def create_screenshot(
    payload: TimeEntryScreenshotCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return TimeEntryScreenshotService.create_screenshot(
        db=db,
        payload=payload,
        current_user=current_user
    )

@router.get("", response_model=List[TimeEntryScreenshotRead])
def list_screenshots(
    time_entry_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return TimeEntryScreenshotService.list_screenshots(
        db=db,
        time_entry_id=time_entry_id,
        user_id=user_id,
        limit=limit,
        current_user=current_user
    )
