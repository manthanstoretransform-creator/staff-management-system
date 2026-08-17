from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

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

    model_config = ConfigDict(from_attributes=True)
