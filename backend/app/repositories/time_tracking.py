from datetime import datetime
from typing import Optional

from sqlalchemy import case, extract, func, select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_status import ProjectStatus, TaskStatus
from app.models.task import Task
from app.models.time_entry import TimeEntry
from app.models.user import User


class TimeTrackingRepository:
    @staticmethod
    def _duration_expression():
        return case(
            (TimeEntry.end_time.is_(None), extract("epoch", func.now() - TimeEntry.start_time)),
            else_=TimeEntry.total_seconds,
        )

    @staticmethod
    def list_daily_totals(
        db: Session,
        organization_id: int,
        start_time: datetime,
        end_time: datetime,
        user_id: Optional[int],
        skip: int,
        limit: int,
    ):
        filters = [
            TimeEntry.organization_id == organization_id,
            TimeEntry.start_time >= start_time,
            TimeEntry.start_time < end_time,
        ]
        if user_id is not None:
            filters.append(TimeEntry.user_id == user_id)

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
                func.sum(TimeTrackingRepository._duration_expression()).label("total_seconds"),
            )
            .join(User, User.id == TimeEntry.user_id)
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
        duration = TimeTrackingRepository._duration_expression().label("duration_seconds")
        query = (
            select(TimeEntry, Project, Task, ProjectStatus, TaskStatus, duration)
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
