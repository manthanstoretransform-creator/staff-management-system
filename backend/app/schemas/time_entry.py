from pydantic import BaseModel, ConfigDict
from datetime import datetime

class TimeEntryStart(BaseModel):
    project_id: int
    task_id: int
    description: str | None = None
    is_billable: bool | None = None

class TimeEntryStop(BaseModel):
    description: str | None = None

class TimeEntryRead(BaseModel):
    id: int
    organization_id: int
    user_id: int
    project_id: int
    task_id: int
    start_time: datetime
    end_time: datetime | None
    total_seconds: int
    status: str
    is_manual: bool
    is_billable: bool
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
