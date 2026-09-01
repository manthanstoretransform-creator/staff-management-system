from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List, Optional


class ActivitySampleCreate(BaseModel):
    """One aggregated capture window from the desktop (60s of sampling)."""
    recorded_at: datetime
    keyboard_strokes: int = Field(..., ge=0)
    mouse_clicks: int = Field(..., ge=0)
    mouse_movements: int = Field(..., ge=0)
    activity_percentage: int = Field(..., ge=0, le=100)
    #: Client-generated idempotency key; a retried upload after a lost
    #: response must not double-insert the same window.
    client_event_id: Optional[str] = Field(None, max_length=255)


class ActivityBatchCreate(BaseModel):
    samples: List[ActivitySampleCreate]


class ActivityResponse(BaseModel):
    id: int
    organization_id: int
    time_entry_id: int
    recorded_at: datetime
    keyboard_strokes: int
    mouse_clicks: int
    mouse_movements: int
    activity_percentage: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
