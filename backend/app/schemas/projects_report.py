from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class BillableFilter(str, Enum):
    billable = "billable"
    non_billable = "non-billable"


class ProjectsReportSummary(BaseModel):
    total_project_hours: float
    total_tracked_seconds: int
    total_hours_formatted: str
    average_activity_percentage: Optional[float] = None
    total_members: int
    total_projects: int


class ProjectsReportItem(BaseModel):
    project_id: int
    project_name: str
    tracked_seconds: int
    tracked_hours: float
    tracked_hours_formatted: str
    activity_percentage: Optional[float] = None


class ProjectsReportResponse(BaseModel):
    start_date: date
    end_date: date
    summary: ProjectsReportSummary
    projects: list[ProjectsReportItem]
