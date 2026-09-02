from datetime import datetime
from typing import List, Optional

from sqlalchemy import Float, case, cast, extract, func, or_, select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_status import ProjectStatus, TaskStatus
from app.models.task import Task
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.repositories.time_entry_adjustment import TimeEntryAdjustmentRepository


class TimeTrackingRepository:
    @staticmethod
    def _duration_expression():
        """Raw measured duration: elapsed-so-far for a running entry,
        `total_seconds` otherwise. Not reportable time on its own -- see
        `_net_duration_expression`."""
        return case(
            (TimeEntry.end_time.is_(None), extract("epoch", func.now() - TimeEntry.start_time)),
            else_=TimeEntry.total_seconds,
        )

    @staticmethod
    def _net_duration_expression(adjustments):
        """Reportable duration for one entry: the measured duration plus its
        net signed `time_entry_adjustments`, floored at zero.

        `time_entries.total_seconds` is never edited, so deductions --
        unwanted-activity penalties, discarded idle time, and idle time
        reassigned to another project -- live in the adjustments table. This
        is the same netting the reports page and the dashboard already apply;
        applying it here too means every surface reports the same number
        instead of time-tracking alone showing the un-deducted figure.
        """
        return func.greatest(
            cast(TimeTrackingRepository._duration_expression(), Float)
            + func.coalesce(cast(adjustments.c.adj_seconds, Float), 0.0),
            0.0,
        )

    @staticmethod
    def list_daily_totals(
        db: Session,
        organization_id: int,
        start_time: datetime,
        end_time: datetime,
        user_ids: Optional[List[int]],
        search: Optional[str],
        skip: int,
        limit: int,
    ):
        filters = [
            TimeEntry.organization_id == organization_id,
            TimeEntry.start_time >= start_time,
            TimeEntry.start_time < end_time,
        ]
        if user_ids:
            filters.append(TimeEntry.user_id.in_(user_ids))
        if search:
            term = f"%{search.strip().lower()}%"
            filters.append(or_(func.lower(User.name).like(term), func.lower(User.email).like(term)))

        adjustments = TimeEntryAdjustmentRepository.net_totals_subquery()
        work_date = func.date(TimeEntry.start_time).label("work_date")
        query = (
            select(
                TimeEntry.user_id.label("employee_id"),
                User.name,
                User.email,
                User.designation,
                work_date,
                func.min(TimeEntry.start_time).label("start_time"),
                func.max(TimeEntry.end_time).label("end_time"),
                func.sum(TimeTrackingRepository._net_duration_expression(adjustments)).label("total_seconds"),
            )
            .join(User, User.id == TimeEntry.user_id)
            .outerjoin(adjustments, adjustments.c.time_entry_id == TimeEntry.id)
            .where(*filters)
            .group_by(TimeEntry.user_id, User.name, User.email, User.designation, work_date)
            .order_by(work_date.desc(), User.name, TimeEntry.user_id)
        )
        total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
        rows = db.execute(query.offset(skip).limit(limit)).mappings().all()
        return list(rows), int(total)

    @staticmethod
    def get_employee(db: Session, organization_id: int, employee_id: int) -> Optional[User]:
        return db.scalar(select(User).where(User.id == employee_id, User.organization_id == organization_id))

    @staticmethod
    def detail_entries(
        db: Session,
        organization_id: int,
        employee_id: int,
        start_time: datetime,
        end_time: datetime,
    ):
        adjustments = TimeEntryAdjustmentRepository.net_totals_subquery()
        duration = TimeTrackingRepository._net_duration_expression(adjustments).label("duration_seconds")
        query = (
            select(TimeEntry, Project, Task, ProjectStatus, TaskStatus, duration)
            .outerjoin(adjustments, adjustments.c.time_entry_id == TimeEntry.id)
            .join(Project, Project.id == TimeEntry.project_id)
            .join(Task, Task.id == TimeEntry.task_id)
            .outerjoin(ProjectStatus, ProjectStatus.id == Project.status_id)
            .outerjoin(TaskStatus, TaskStatus.id == Task.status_id)
            .where(
                TimeEntry.organization_id == organization_id,
                TimeEntry.user_id == employee_id,
                Project.organization_id == organization_id,
                Task.organization_id == organization_id,
                TimeEntry.start_time >= start_time,
                TimeEntry.start_time < end_time,
            )
            .order_by(TimeEntry.start_time, TimeEntry.id)
        )
        return db.execute(query).all()
