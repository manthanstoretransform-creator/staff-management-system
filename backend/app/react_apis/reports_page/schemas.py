"""Pydantic schemas for the React Reports page APIs.

Every one of the four report tabs (Project / Task / App / URL) returns the
same metric shape -- ``total_hours``, ``avg_activity``, ``total_members``,
``total_tasks`` -- alongside the entity's own id/name, so the frontend can
render all four tabs with one table component.
"""

from enum import Enum
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

ItemT = TypeVar("ItemT")


class SortField(str, Enum):
    """Whitelisted sort keys. Client-supplied strings are never interpolated
    into an ORDER BY -- they are mapped through this enum to a column."""

    total_hours = "total_hours"
    avg_activity = "avg_activity"
    total_members = "total_members"
    total_tasks = "total_tasks"
    name = "name"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


class ReportMetrics(BaseModel):
    total_hours: float = Field(
        ...,
        description="Tracked time in hours, rounded to 2 decimals. Derived from the same "
                    "reportable-seconds definition the rest of the backend uses: timer entries "
                    "(plus any still-running entry's elapsed time), approved manual entries that "
                    "have not been mirrored into time_entries, and signed time_entry_adjustments.",
        examples=[42.75],
    )
    avg_activity: Optional[float] = Field(
        None,
        description="Average of time_entry_activity.activity_percentage (0-100) over the activity "
                    "samples in scope, weighted by sample count. Null when nothing in scope was "
                    "activity-sampled -- rows without samples never drag the average toward zero.",
        examples=[71.32],
    )
    total_members: int = Field(..., description="COUNT(DISTINCT user id) in scope.", examples=[5])
    total_tasks: int = Field(..., description="COUNT(DISTINCT task id) in scope.", examples=[14])


class ReportSummary(ReportMetrics):
    """Metrics for the whole filtered scope -- the Reports page's header strip.
    Shared by all four tabs."""


class ProjectReportItem(ReportMetrics):
    project_id: int
    project_name: str


class TaskReportItem(ReportMetrics):
    task_id: int
    task_name: str
    total_tasks: int = Field(
        1,
        description="Always 1: a task row represents exactly one task, not a count of its "
                    "tracking rows.",
    )


class AppReportItem(ReportMetrics):
    app_id: str = Field(
        ...,
        description="There is no applications table in this schema -- time_entry_app_usage "
                    "identifies an application by its name, so that name is the app's identifier. "
                    "Returned as a string, and equal to app_name, rather than inventing a "
                    "synthetic numeric id.",
        examples=["Google Chrome"],
    )
    app_name: str


class UrlReportItem(ReportMetrics):
    url_id: str = Field(
        ...,
        description="There is no urls table in this schema -- time_entry_url_usage identifies a "
                    "site by its domain, so that domain is the URL's identifier. Returned as a "
                    "string, and equal to url_name.",
        examples=["github.com"],
    )
    url_name: str


class Page(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    page: int = Field(..., examples=[1])
    limit: int = Field(..., examples=[20])
    total: int = Field(..., description="Total matching rows across all pages.", examples=[100])
    pages: int = Field(..., description="Total number of pages at this limit.", examples=[5])


ProjectReportPage = Page[ProjectReportItem]
TaskReportPage = Page[TaskReportItem]
AppReportPage = Page[AppReportItem]
UrlReportPage = Page[UrlReportItem]
