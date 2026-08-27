from datetime import date, datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.manual_time_entry import ManualTimeEntry
from app.models.project import Project
from app.models.time_entry import TimeEntry
from app.models.time_entry_activity import TimeEntryActivity
from app.repositories.time_tracking import TimeTrackingRepository


class ProjectsReportRepository:
    """Query support for the Projects Report API.

    Reuses TimeTrackingRepository._duration_expression() rather than
    reimplementing "seconds tracked, counting a still-running entry as
    elapsed-so-far" a second time (see CLAUDE.md rule #1).
    """

    @staticmethod
    def eligible_projects(
        db: Session,
        organization_id: int,
        project_ids: Optional[list[int]],
        is_billable: Optional[bool],
    ) -> dict[int, str]:
        filters = [Project.organization_id == organization_id]
        if project_ids:
            filters.append(Project.id.in_(project_ids))
        if is_billable is not None:
            filters.append(Project.is_billable.is_(is_billable))
        rows = db.execute(
            select(Project.id, Project.project_name).where(*filters).order_by(Project.project_name)
        ).all()
        return {row.id: row.project_name for row in rows}

    @staticmethod
    def hours_by_project(
        db: Session,
        organization_id: int,
        project_ids: list[int],
        member_ids: Optional[list[int]],
        start_time: datetime,
        end_time: datetime,
    ) -> dict[int, int]:
        if not project_ids:
            return {}
        filters = [
            TimeEntry.organization_id == organization_id,
            TimeEntry.project_id.in_(project_ids),
            TimeEntry.start_time >= start_time,
            TimeEntry.start_time < end_time,
        ]
        if member_ids:
            filters.append(TimeEntry.user_id.in_(member_ids))
        query = (
            select(TimeEntry.project_id, func.sum(TimeTrackingRepository._duration_expression()).label("secs"))
            .where(*filters)
            .group_by(TimeEntry.project_id)
        )
        return {row.project_id: int(row.secs or 0) for row in db.execute(query).all()}

    @staticmethod
    def manual_hours_by_project(
        db: Session,
        organization_id: int,
        project_ids: list[int],
        member_ids: Optional[list[int]],
        start_date: date,
        end_date: date,
    ) -> dict[int, int]:
        if not project_ids:
            return {}
        filters = [
            ManualTimeEntry.organization_id == organization_id,
            ManualTimeEntry.project_id.in_(project_ids),
            ManualTimeEntry.approval_status == "approved",
            ManualTimeEntry.work_date >= start_date,
            ManualTimeEntry.work_date <= end_date,
        ]
        if member_ids:
            filters.append(ManualTimeEntry.user_id.in_(member_ids))
        query = (
            select(ManualTimeEntry.project_id, func.sum(ManualTimeEntry.total_seconds).label("secs"))
            .where(*filters)
            .group_by(ManualTimeEntry.project_id)
        )
        return {row.project_id: int(row.secs or 0) for row in db.execute(query).all()}

    @staticmethod
    def activity_by_project(
        db: Session,
        organization_id: int,
        project_ids: list[int],
        member_ids: Optional[list[int]],
        start_time: datetime,
        end_time: datetime,
    ) -> dict[int, tuple[float, int]]:
        """Average activity_percentage per project, plus the sample count backing it.

        Joins time_entry_activity -> time_entries so the samples averaged are
        the same entries counted in hours_by_project. Returns {} for every
        project until the desktop's activity batch-sync exists (see
        CLAUDE.md Known open items #1) -- that's an honest empty result, not
        a bug in this query.
        """
        if not project_ids:
            return {}
        filters = [
            TimeEntry.organization_id == organization_id,
            TimeEntry.project_id.in_(project_ids),
            TimeEntry.start_time >= start_time,
            TimeEntry.start_time < end_time,
        ]
        if member_ids:
            filters.append(TimeEntry.user_id.in_(member_ids))
        query = (
            select(
                TimeEntry.project_id,
                func.avg(TimeEntryActivity.activity_percentage).label("avg_pct"),
                func.count(TimeEntryActivity.id).label("sample_count"),
            )
            .join(TimeEntryActivity, TimeEntryActivity.time_entry_id == TimeEntry.id)
            .where(*filters)
            .group_by(TimeEntry.project_id)
        )
        return {row.project_id: (float(row.avg_pct), int(row.sample_count)) for row in db.execute(query).all()}

    @staticmethod
    def distinct_member_ids(
        db: Session,
        organization_id: int,
        project_ids: list[int],
        member_ids: Optional[list[int]],
        start_time: datetime,
        end_time: datetime,
        start_date: date,
        end_date: date,
    ) -> set[int]:
        if not project_ids:
            return set()
        auto_filters = [
            TimeEntry.organization_id == organization_id,
            TimeEntry.project_id.in_(project_ids),
            TimeEntry.start_time >= start_time,
            TimeEntry.start_time < end_time,
        ]
        manual_filters = [
            ManualTimeEntry.organization_id == organization_id,
            ManualTimeEntry.project_id.in_(project_ids),
            ManualTimeEntry.approval_status == "approved",
            ManualTimeEntry.work_date >= start_date,
            ManualTimeEntry.work_date <= end_date,
        ]
        if member_ids:
            auto_filters.append(TimeEntry.user_id.in_(member_ids))
            manual_filters.append(ManualTimeEntry.user_id.in_(member_ids))

        auto_ids = db.execute(select(TimeEntry.user_id.distinct()).where(*auto_filters)).scalars().all()
        manual_ids = db.execute(select(ManualTimeEntry.user_id.distinct()).where(*manual_filters)).scalars().all()
        return set(auto_ids) | set(manual_ids)
