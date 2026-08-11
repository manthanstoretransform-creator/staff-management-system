from pydantic import BaseModel, ConfigDict
from datetime import date, datetime

class ManualTimeEntryCreate(BaseModel):
    project_id: int
    task_id: int
    work_date: date
    start_time: datetime
    end_time: datetime
    total_seconds: int
    description: str | None = None
    is_billable: bool | None = True

class ManualTimeEntryApprovalUpdate(BaseModel):
    pass

class ManualTimeEntryRead(BaseModel):
    id: int
    organization_id: int
    user_id: int
    project_id: int
    task_id: int
    work_date: date
    start_time: datetime
    end_time: datetime
    total_seconds: int
    description: str | None
    is_billable: bool
    approval_status: str
    approved_by: int | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
