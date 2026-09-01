from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional


class UnwantedActivityCreate(BaseModel):
    """One detection event from the desktop's rule engine (a rule threshold
    being crossed once, e.g. "CTRL pressed 15+ times in the rule window").

    user/organization/project/task are NOT accepted from the client -- the
    backend derives all four from the authenticated user and the time
    entry itself, so an event can never be attributed across users."""
    activity_type: str = Field(..., max_length=50, min_length=1)
    key_or_action: str = Field(..., max_length=100, min_length=1)
    occurrence_count: int = Field(..., ge=1)
    alerted: bool = False
    alert_count: int = Field(0, ge=0)
    recorded_at: Optional[datetime] = None
    client_event_id: Optional[str] = Field(None, max_length=255)


class UnwantedActivityResponse(BaseModel):
    id: int
    organization_id: int
    user_id: int
    project_id: int
    task_id: int
    time_entry_id: int
    activity_type: str
    key_or_action: str
    occurrence_count: int
    alerted: bool
    alert_count: int
    recorded_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
