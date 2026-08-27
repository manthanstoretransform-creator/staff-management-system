from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.user import User
from app.schemas.projects_report import BillableFilter, ProjectsReportResponse
from app.services.projects_report import ProjectsReportService

# Self-contained /api/v1 prefix, registered once in app.main alongside
# project_management/teams/time_tracking -- see app/main.py section 3.
router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


@router.get(
    "/projects",
    response_model=ProjectsReportResponse,
    dependencies=[Depends(require_permission("time_entries:view_all"))],
    summary="Projects report: routed hours and activity by project, filtered by date range, members, projects and billing type",
)
def projects_report(
    from_date: date = Query(..., alias="from", description="Start of the report date range (inclusive)."),
    to_date: date = Query(..., alias="to", description="End of the report date range (inclusive)."),
    member_ids: Optional[list[int]] = Query(None, alias="member_id", description="Repeat to select multiple members, e.g. ?member_id=1&member_id=2. Omit for all members."),
    project_ids: Optional[list[int]] = Query(None, alias="project_id", description="Repeat to select multiple projects. Omit for all projects."),
    billing_type: Optional[BillableFilter] = Query(None, description="Filter to billable or non-billable projects only. Omit for both."),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ProjectsReportService.build(
        db, current_user, from_date, to_date, member_ids, project_ids, billing_type
    )
