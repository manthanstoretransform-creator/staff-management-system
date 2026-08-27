from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.schemas.reports import (
    BillableFilter,
    DetailedLogsResponse,
    GroupedReportResponse,
    ReportDimension,
    SortField,
    UsageType,
)
from app.services.reports import ReportsService

# Self-contained /api/v1 prefix, registered once in app.main alongside
# project_management/teams/time_tracking -- see app/main.py section 3.
router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])

_view_all = Depends(require_permission("time_entries:view_all"))


def _filters(
    from_date: date = Query(..., alias="from", description="Start of the report date range (inclusive)."),
    to_date: date = Query(..., alias="to", description="End of the report date range (inclusive)."),
    member_ids: Optional[list[int]] = Query(None, alias="member_id", description="Repeat to select multiple members, e.g. ?member_id=1&member_id=2. Omit for all members."),
    project_ids: Optional[list[int]] = Query(None, alias="project_id", description="Repeat to select multiple projects. Omit for all projects."),
    billing_type: Optional[BillableFilter] = Query(None, description="Filter to billable or non-billable projects only. Omit for both."),
):
    return from_date, to_date, member_ids, project_ids, billing_type


@router.get(
    "/projects",
    response_model=GroupedReportResponse,
    dependencies=[_view_all],
    summary="Projects report grouped by project: routed hours and activity, filtered by date range, members, projects and billing type",
)
def projects_report(filters=Depends(_filters), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from_date, to_date, member_ids, project_ids, billing_type = filters
    return ReportsService.build_grouped(
        db, current_user, ReportDimension.projects, from_date, to_date, member_ids, project_ids, billing_type, UsageType.app
    )


@router.get(
    "/members",
    response_model=GroupedReportResponse,
    dependencies=[_view_all],
    summary="Members report grouped by member: routed hours and activity per member",
)
def members_report(filters=Depends(_filters), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from_date, to_date, member_ids, project_ids, billing_type = filters
    return ReportsService.build_grouped(
        db, current_user, ReportDimension.members, from_date, to_date, member_ids, project_ids, billing_type, UsageType.app
    )


@router.get(
    "/tasks",
    response_model=GroupedReportResponse,
    dependencies=[_view_all],
    summary="Tasks report grouped by task: routed hours and activity per task",
)
def tasks_report(filters=Depends(_filters), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from_date, to_date, member_ids, project_ids, billing_type = filters
    return ReportsService.build_grouped(
        db, current_user, ReportDimension.tasks, from_date, to_date, member_ids, project_ids, billing_type, UsageType.app
    )


@router.get(
    "/apps",
    response_model=GroupedReportResponse,
    dependencies=[_view_all],
    summary="Apps/URLs usage report grouped by application (usage_type=app) or domain (usage_type=url)",
)
def apps_report(
    filters=Depends(_filters),
    usage_type: UsageType = Query(UsageType.app, description="Group by application (app) or by domain (url)."),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from_date, to_date, member_ids, project_ids, billing_type = filters
    return ReportsService.build_grouped(
        db, current_user, ReportDimension.apps, from_date, to_date, member_ids, project_ids, billing_type, usage_type
    )


@router.get(
    "/detailed-logs",
    response_model=DetailedLogsResponse,
    dependencies=[_view_all],
    summary="Paginated row-by-row activity log backing a report page's detail table",
)
def detailed_logs(
    filters=Depends(_filters),
    dimension: ReportDimension = Query(ReportDimension.projects, description="Which report page this table belongs to. projects/members/tasks all return the same session-grain rows (app/url are null); apps returns per-app/per-URL usage rows instead."),
    usage_type: UsageType = Query(UsageType.app, description="Only used when dimension=apps."),
    search: Optional[str] = Query(None, max_length=200, description="Case-insensitive match against member, project, task, and (for dimension=apps) app/domain."),
    sort_by: SortField = Query(SortField.date),
    sort_desc: bool = Query(True),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from_date, to_date, member_ids, project_ids, billing_type = filters
    return ReportsService.build_detailed_logs(
        db, current_user, dimension, from_date, to_date, member_ids, project_ids, billing_type, usage_type,
        search, sort_by.value, sort_desc, page, limit,
    )
