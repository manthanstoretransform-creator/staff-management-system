from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from typing import Optional

class ProjectBase(BaseModel):
    project_name: str
    description: Optional[str] = None
    status: str = "planning"
    start_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    is_billable: bool = True
    time_tracked_seconds: int = 0

class ProjectCreate(BaseModel):
    project_name: str
    description: Optional[str] = None
    start_date: Optional[date] = None
    is_billable: bool = True

class ProjectUpdate(BaseModel):
    project_name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    is_billable: Optional[bool] = None

class ProjectRead(ProjectBase):
    id: int
    organization_id: int
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
