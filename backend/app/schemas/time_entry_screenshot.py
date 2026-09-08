from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import List, Optional


class TimeEntryScreenshotBase(BaseModel):
    monitor_number: int = 1


class TimeEntryScreenshotCreate(TimeEntryScreenshotBase):
    time_entry_id: int
    file_path: str
    captured_at: Optional[datetime] = None


class TimeEntryScreenshotRead(TimeEntryScreenshotBase):
    id: int
    organization_id: int
    time_entry_id: int
    captured_at: datetime
    file_path: str
    created_at: datetime

    #: Storage metadata. Optional on read because rows that predate the Drive
    #: pipeline carry none of it, and a listing must not fail on them.
    google_drive_file_id: Optional[str] = None
    file_name: Optional[str] = None
    file_size_bytes: Optional[int] = None
    mime_type: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    upload_status: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    client_screenshot_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ScreenshotUploadResponse(BaseModel):
    """Answer to a desktop upload.

    `duplicate` is true when the request carried a `client_screenshot_id` that
    had already been stored — a retry after a lost response. The client treats
    it exactly as a success and deletes its local copy, which is the point: the
    image is safely stored either way.
    """

    success: bool = True
    duplicate: bool = False
    screenshot: TimeEntryScreenshotRead


class ScreenshotDeleteResponse(BaseModel):
    """Answer to a successful deletion.

    Reports the id that was removed so a client acting on a grid selection can
    reconcile its own list without a refetch. There is no partial success: this
    response is only produced once both the Drive object and the metadata row
    are gone.
    """

    success: bool = True
    message: str = "Screenshot deleted successfully."
    screenshot_id: int


class ScreenshotView(BaseModel):
    """One screenshot as the timeline and grid render it."""

    id: int
    captured_at: datetime
    monitor_number: int
    width: Optional[int] = None
    height: Optional[int] = None
    file_size_bytes: Optional[int] = None
    #: Backend path that streams the image, subject to the same permission
    #: check as this response. Never a Google Drive link.
    view_url: str

    model_config = ConfigDict(from_attributes=True)


class ScreenshotTimelineWindow(BaseModel):
    """One fixed-length window of the tracked day.

    `activity_percentage` is the duration-weighted activity of the
    `time_entry_activity` rows recorded inside this window, and nothing else —
    never the day's or the entry's overall figure. A window with no activity
    rows reports `activity_measured_seconds = 0`, which is how a caller tells
    "0% activity" from "nothing was measured".
    """

    window_start: datetime
    window_end: datetime
    activity_percentage: int = Field(ge=0, le=100)
    activity_measured_seconds: int
    screenshots: List[ScreenshotView]
    screenshot_count: int


class ScreenshotTimelineResponse(BaseModel):
    success: bool = True
    window_minutes: int
    windows: List[ScreenshotTimelineWindow]
