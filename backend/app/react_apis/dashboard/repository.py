"""Dashboard-specific aggregation.

Everything that the Reports page already defines -- the filter set, the
entry-grain subquery (one row per contributing time entry, with reportable
seconds and activity carried as sum/count), the grouped project/member/app
queries, pagination and sorting -- is imported from
``app.react_apis.reports_page`` rather than reimplemented, so the Dashboard
and Reports can never disagree about hours or activity for the same filters.

Only three things are genuinely new here:

* ``summary`` -- the Reports summary plus an active-project count.
* ``time_series`` -- tracked seconds per IST calendar day.
* ``top_apps`` -- the app usage rows plus the overall app-hours denominator
  the donut chart needs.
"""

from datetime import date
from typing import Optional

from sqlalchemy import Date, Float, case, cast, distinct, func, select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.react_apis.reports_page.repository import ReportFilters, ReportsPageRepository

#: Projects in this status are excluded from the "active projects" card. The
#: projects table already carries active/todo/pending/completed/archived --
#: no new status is introduced for the dashboard.
ARCHIVED_PROJECT_STATUS = "archived"


class DashboardRepository:
    @staticmethod
    def summary(db: Session, filters: ReportFilters):
        """Total hours, average activity, distinct members, distinct tasks and
        distinct non-archived projects -- all from the one entry-grain scan."""
        entries = ReportsPageRepository.entry_grain_subquery(filters)
        # Only projects that are still live count toward the card; an archived
        # project's tracked time still counts toward total hours.
        active_projects = func.count(
            distinct(
                case(
                    (Project.status != ARCHIVED_PROJECT_STATUS, entries.c.project_id),
                    else_=None,
                )
            )
        )
        query = (
            select(
                *ReportsPageRepository._metric_columns(entries),
                active_projects.label("active_projects"),
            )
            .select_from(entries)
            # 1:1 with project_id, so this join cannot fan the entry rows out.
            .join(Project, Project.id == entries.c.project_id)
        )
        return db.execute(query).one()

    @staticmethod
    def time_series(
        db: Session, filters: ReportFilters, interval: str = "day"
    ) -> dict[date, tuple[float, float]]:
        """Tracked and manual seconds per bucket, keyed by the bucket's first
        IST calendar day.

        Returns only the buckets that actually have data -- the service fills
        the gaps, so the chart's X-axis stays continuous without the database
        having to generate a date series.
        """
        entries = ReportsPageRepository.entry_grain_subquery(filters)
        bucket = (
            entries.c.work_date
            if interval == "day"
            else cast(func.date_trunc(interval, entries.c.work_date), Date)
        )
        manual_seconds = func.sum(
            case((entries.c.is_manual, entries.c.seconds), else_=cast(0, Float))
        )
        query = (
            select(
                bucket.label("bucket"),
                func.coalesce(func.sum(entries.c.seconds), 0.0).label("total_seconds"),
                func.coalesce(manual_seconds, 0.0).label("manual_seconds"),
            )
            .select_from(entries)
            .group_by(bucket)
        )
        return {
            row.bucket: (float(row.total_seconds or 0), float(row.manual_seconds or 0))
            for row in db.execute(query).all()
        }

    @staticmethod
    def top_apps(
        db: Session,
        filters: ReportFilters,
        search: Optional[str],
        sort_by: str,
        sort_order: str,
        page: int,
        limit: int,
    ):
        return ReportsPageRepository.usage(
            db, filters, "app", search, sort_by, sort_order, page, limit
        )

    @staticmethod
    def total_app_seconds(db: Session, filters: ReportFilters, search: Optional[str]) -> float:
        """Denominator for the donut chart's percentages: app usage seconds
        across the whole filtered scope, not just the page being shown."""
        return ReportsPageRepository.usage_total_seconds(db, filters, "app", search)
