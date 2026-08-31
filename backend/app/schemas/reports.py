from datetime import date
from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel

from app.schemas.project_management import StatusRead


class BillableFilter(str, Enum):
    billable = "billable"
    non_billable = "non-billable"


class UsageType(str, Enum):
    app = "app"
    url = "url"


class ReportDimension(str, Enum):
    projects = "projects"
    members = "members"
    tasks = "tasks"
    apps = "apps"


class SortField(str, Enum):
    date = "date"
    member = "member"
    project = "project"
    task = "task"
    hours = "hours"
    activity = "activity"


class ReportSummary(BaseModel):
    total_hours: float
    total_tracked_seconds: int
    total_hours_formatted: str
    average_activity_percentage: Optional[float] = None
    total_members: int
    total_entries: int
    # Only the field matching the endpoint's own dimension is populated;
    # the rest stay null (e.g. /reports/members never sets total_projects).
    total_projects: Optional[int] = None
    total_tasks: Optional[int] = None
    total_apps: Optional[int] = None


class GroupedItem(BaseModel):
    id: Union[int, str]
    name: str
    tracked_seconds: int
    tracked_hours: float
    tracked_hours_formatted: str
    activity_percentage: Optional[float] = None
    meta_label: str


class GroupedReportResponse(BaseModel):
    start_date: date
    end_date: date
    summary: ReportSummary
    grouped_data: list[GroupedItem]


class DetailedLogItem(BaseModel):
    id: str
    date: date
    member_id: int
    member_name: str
    role: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    task_id: Optional[int] = None
    task_name: Optional[str] = None
    app: Optional[str] = None
    url: Optional[str] = None
    tracked_hours: float
    activity_percentage: Optional[float] = None


class DetailedLogsPagination(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


class DetailedLogsResponse(BaseModel):
    start_date: date
    end_date: date
    items: list[DetailedLogItem]
    pagination: DetailedLogsPagination


class ProjectTaskSummaryTask(BaseModel):
    id: int
    task_name: str
    task_created_date: date
    total_tracked_hours: float


class ProjectTaskSummaryProject(BaseModel):
    id: int
    project_name: str
    created_date: date
    status: Optional[StatusRead] = None
    total_task_count: int
    total_task_hours: float
    tasks: list[ProjectTaskSummaryTask]


class ProjectTaskSummaryPagination(BaseModel):
    page: int
    limit: int
    total_projects: int
    total_pages: int


class ProjectTaskSummaryResponse(BaseModel):
    projects: list[ProjectTaskSummaryProject]
    pagination: ProjectTaskSummaryPagination
