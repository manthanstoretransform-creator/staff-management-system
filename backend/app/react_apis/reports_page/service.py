"""Filter resolution, validation and response shaping for the Reports page APIs.

All SQL aggregation lives in ``repository.py``; this layer only resolves the
default date window, validates the request, and turns aggregate rows into the
response schemas.
"""

from datetime import date, timedelta
from math import ceil
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.time_format import ist_day_end_utc, ist_day_start_utc, ist_today
from app.models.user import User
from app.react_apis.reports_page.repository import ReportFilters, ReportsPageRepository

#: The Reports page defaults to the last 7 *calendar* days including today --
#: today-6 .. today inclusive, not the previous seven 24-hour periods.
DEFAULT_RANGE_DAYS = 7


class ReportsPageService:
    @staticmethod
    def resolve_filters(
        current_user: User,
        start_date: Optional[date],
        end_date: Optional[date],
        project_id: Optional[int],
        task_id: Optional[int],
        member_id: Optional[int],
    ) -> ReportFilters:
        """Apply the default window, validate the range, and scope to the
        authenticated user's organization.

        The tenant scope is taken from ``current_user`` only -- an
        organization id supplied by the frontend is never trusted or read.
        """
        # "Today" is the IST calendar day, matching the IST windows the range
        # is resolved into -- not the server's local date.
        today = ist_today()
        if end_date is None:
            end_date = today
        if start_date is None:
            start_date = end_date - timedelta(days=DEFAULT_RANGE_DAYS - 1)
        if start_date > end_date:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "start_date cannot be after end_date.",
            )
        return ReportFilters(
            organization_id=current_user.organization_id,
            start_date=start_date,
            end_date=end_date,
            # Half-open UTC bounds of the IST calendar range, so activity
            # recorded late on end_date is still inside the window.
            start_time=ist_day_start_utc(start_date),
            end_time=ist_day_end_utc(end_date),
            project_id=project_id,
            task_id=task_id,
            member_id=member_id,
        )

    # ------------------------------------------------------------------ shaping

    @staticmethod
    def _metrics(row) -> dict:
        return {
            "total_hours": round(float(row.total_seconds or 0) / 3600, 2),
            "avg_activity": None if row.avg_activity is None else round(float(row.avg_activity), 2),
            "total_members": int(row.total_members or 0),
            "total_tasks": int(row.total_tasks or 0),
        }

    @staticmethod
    def _page(items: list[dict], page: int, limit: int, total: int) -> dict:
        return {
            "items": items,
            "page": page,
            "limit": limit,
            "total": total,
            "pages": ceil(total / limit) if total else 0,
        }

    # ---------------------------------------------------------------- endpoints

    @staticmethod
    def summary(db: Session, filters: ReportFilters) -> dict:
        return ReportsPageService._metrics(ReportsPageRepository.summary(db, filters))

    @staticmethod
    def _entity_page(rows, total, page, limit, id_field, name_field) -> dict:
        items = [
            {
                id_field: row.id,
                name_field: row.name,
                **ReportsPageService._metrics(row),
            }
            for row in rows
        ]
        return ReportsPageService._page(items, page, limit, total)

    @staticmethod
    def projects(db, filters, search, sort_by, sort_order, page, limit) -> dict:
        rows, total = ReportsPageRepository.projects(db, filters, search, sort_by, sort_order, page, limit)
        return ReportsPageService._entity_page(rows, total, page, limit, "project_id", "project_name")

    @staticmethod
    def tasks(db, filters, search, sort_by, sort_order, page, limit) -> dict:
        rows, total = ReportsPageRepository.tasks(db, filters, search, sort_by, sort_order, page, limit)
        # total_tasks is COUNT(DISTINCT task_id) grouped by task_id, so it is
        # already 1 per row -- a task record is one task, never a count of its
        # tracking rows.
        return ReportsPageService._entity_page(rows, total, page, limit, "task_id", "task_name")

    @staticmethod
    def apps(db, filters, search, sort_by, sort_order, page, limit) -> dict:
        rows, total = ReportsPageRepository.usage(db, filters, "app", search, sort_by, sort_order, page, limit)
        return ReportsPageService._entity_page(rows, total, page, limit, "app_id", "app_name")

    @staticmethod
    def urls(db, filters, search, sort_by, sort_order, page, limit) -> dict:
        rows, total = ReportsPageRepository.usage(db, filters, "url", search, sort_by, sort_order, page, limit)
        return ReportsPageService._entity_page(rows, total, page, limit, "url_id", "url_name")
