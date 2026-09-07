from fastapi import APIRouter, Depends, File, Form, Path, Query, Response, UploadFile, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.time_entry_screenshot import (
    ScreenshotTimelineResponse, ScreenshotUploadResponse,
    TimeEntryScreenshotCreate, TimeEntryScreenshotRead,
)
from app.services.time_entry_screenshot import TimeEntryScreenshotService

router = APIRouter(tags=["Time Entry Screenshots"])


@router.post(
    "/time-entries/{time_entry_id}/screenshots",
    response_model=ScreenshotUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload one captured screenshot",
)
async def upload_screenshot(
    time_entry_id: int = Path(..., gt=0),
    file: UploadFile = File(..., description="The 1000x1000 WebP image"),
    client_screenshot_id: str = Form(..., description="Client-generated UUID; the idempotency key"),
    captured_at: Optional[datetime] = Form(None),
    monitor_number: int = Form(1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store a screenshot captured by the desktop client.

    The image goes to Google Drive under Year/Month/User_<id>/Date, created on
    demand, and the metadata lands here. Organization and user are taken from
    the authenticated session and the time entry — never from the request.

    Idempotent on `client_screenshot_id`: the desktop queues captures offline
    and retries with backoff, so a response lost after the file was stored must
    not produce a second Drive file. A repeat returns the original record with
    `duplicate: true`, which the client treats as success.
    """
    content = await file.read()
    record, duplicate = TimeEntryScreenshotService.upload_screenshot(
        db=db,
        time_entry_id=time_entry_id,
        content=content,
        content_type=file.content_type,
        client_screenshot_id=client_screenshot_id,
        current_user=current_user,
        captured_at=captured_at,
        monitor_number=monitor_number,
    )
    return {
        "success": True,
        "duplicate": duplicate,
        "screenshot": TimeEntryScreenshotRead.model_validate(record),
    }


@router.get(
    "/time-entry-screenshots/timeline",
    response_model=ScreenshotTimelineResponse,
    summary="Screenshots and per-window activity for one day",
)
def get_screenshot_timeline(
    user_id: Optional[int] = Query(None, description="Defaults to the caller"),
    target_date: Optional[date] = Query(None, alias="date", description="IST calendar date"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """A day as fixed windows, each carrying its own screenshots and its own
    activity percentage.

    The activity figure is computed from the `time_entry_activity` rows
    recorded *inside that window*, duration-weighted — it is never the day's or
    the entry's overall number. `activity_measured_seconds` is returned
    alongside it so a caller can tell a measured 0% from an unmeasured window.

    Windows are derived from timestamps, so `screenshot_count` reflects however
    many captures the client's configuration produced: one today, three or five
    if that setting changes, with no change here.
    """
    window_minutes, windows = TimeEntryScreenshotService.get_timeline(
        db=db, current_user=current_user, user_id=user_id, target_date=target_date
    )
    return {"success": True, "window_minutes": window_minutes, "windows": windows}


@router.get(
    "/time-entry-screenshots/{screenshot_id}/view",
    summary="Stream one screenshot image",
    response_class=Response,
)
def view_screenshot(
    screenshot_id: int = Path(..., gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the image bytes for an authorised caller.

    Proxied through this endpoint rather than redirected to Drive: a Drive link
    would outlive the permission check that produced it, and serving one would
    mean making the storage folder publicly readable. A screenshot the caller
    may not see answers 404, not 403 — a 403 on a guessed id would confirm the
    id exists, which is itself information about someone else's day.
    """
    content, mime_type, file_name = TimeEntryScreenshotService.get_screenshot_bytes(
        db=db, screenshot_id=screenshot_id, current_user=current_user
    )
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{file_name}"',
            # Screenshots never change once stored, but they are private, so
            # they may only be held by the browser that fetched them.
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.post("/time-entry-screenshots", response_model=TimeEntryScreenshotRead, status_code=status.HTTP_201_CREATED)
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


@router.get("/time-entry-screenshots", response_model=List[TimeEntryScreenshotRead])
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
