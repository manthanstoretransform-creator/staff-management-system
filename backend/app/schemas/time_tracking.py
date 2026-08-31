from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TimeTrackingStatus(BaseModel):
    id: int
    name: str
    color: str
    model_config = ConfigDict(from_attributes=True)


class TimeTrackingListItem(BaseModel):
    employee_id: int
    name: str
    email: Optional[str] = None
    designation: Optional[str] = None
    date: date
    start_time: datetime
    end_time: Optional[datetime] = None
    total_seconds: int
    total_hours: str


class TimeTrackingListResponse(BaseModel):
    items: list[TimeTrackingListItem]
    pagination: dict


class TimeTrackingEntry(BaseModel):
    id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: int
    is_running: bool
    is_manual: bool


class TimeTrackingTask(BaseModel):
    id: int
    name: str
    status: Optional[TimeTrackingStatus] = None
    total_seconds: int
    total_hours: str
    entries: list[TimeTrackingEntry]


class TimeTrackingProject(BaseModel):
    id: int
    name: str
    status: Optional[TimeTrackingStatus] = None
    total_seconds: int
    total_hours: str
    tasks: list[TimeTrackingTask]


class TimeTrackingSummary(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_seconds: int
    total_hours: str


class TimeTrackingEmployee(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    designation: Optional[str] = None
    role: Optional[str] = None


class TimeTrackingDetailResponse(BaseModel):
    employee: TimeTrackingEmployee
    start_date: date
    end_date: date
    summary: TimeTrackingSummary
    projects: list[TimeTrackingProject]
