from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func
from typing import List, Optional, Tuple
from datetime import datetime, timezone
from app.models.time_entry_app_usage import TimeEntryAppUsage
from app.models.time_entry import TimeEntry
from app.schemas.time_entry_app_usage import AppUsageCreate
from app.core.validation import LIKE_ESCAPE_CHARACTER, like_pattern

class TimeEntryAppUsageRepository:
    @staticmethod
    def create(
        db: Session,
        organization_id: int,
        time_entry_id: int,
        application_name: str,
        window_title: Optional[str],
        duration_seconds: int,
        recorded_at: Optional[datetime] = None
    ) -> TimeEntryAppUsage:
        db_usage = TimeEntryAppUsage(
            organization_id=organization_id,
            time_entry_id=time_entry_id,
            application_name=application_name,
            window_title=window_title,
            duration_seconds=duration_seconds,
            recorded_at=recorded_at if recorded_at is not None else datetime.now(timezone.utc)
        )
        db.add(db_usage)
        db.commit()
        db.refresh(db_usage)
        return db_usage

    @staticmethod
    def create_batch(
        db: Session,
        organization_id: int,
        time_entry_id: int,
        records: List[AppUsageCreate]
    ) -> List[TimeEntryAppUsage]:
        now_utc = datetime.now(timezone.utc)
        db_records = []
        for r in records:
            db_usage = TimeEntryAppUsage(
                organization_id=organization_id,
                time_entry_id=time_entry_id,
                application_name=r.application_name,
                window_title=r.window_title,
                duration_seconds=r.duration_seconds,
                recorded_at=r.recorded_at if r.recorded_at is not None else now_utc
            )
            db.add(db_usage)
            db_records.append(db_usage)
        
        db.commit()
        for r in db_records:
            db.refresh(r)
        return db_records

    @staticmethod
    def list_by_filters(
        db: Session,
        organization_id: int,
        user_id: Optional[int] = None,
        time_entry_id: Optional[int] = None,
        application_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[TimeEntryAppUsage], int]:
        conditions = [TimeEntryAppUsage.organization_id == organization_id]
        
        query = select(TimeEntryAppUsage)
        
        # If filtering by user_id, we need to join TimeEntry
        if user_id is not None:
            query = query.join(TimeEntry, TimeEntryAppUsage.time_entry_id == TimeEntry.id)
            conditions.append(TimeEntry.user_id == user_id)
            
        if time_entry_id is not None:
            conditions.append(TimeEntryAppUsage.time_entry_id == time_entry_id)
        if application_name is not None:
            conditions.append(TimeEntryAppUsage.application_name.ilike(
                like_pattern(application_name), escape=LIKE_ESCAPE_CHARACTER
            ))
        if start_date is not None:
            conditions.append(TimeEntryAppUsage.recorded_at >= start_date)
        if end_date is not None:
            conditions.append(TimeEntryAppUsage.recorded_at <= end_date)
            
        query = query.where(and_(*conditions))
        
        count = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        
        results = db.scalars(query.order_by(TimeEntryAppUsage.recorded_at.desc()).offset(skip).limit(limit)).all()
        return list(results), count

    @staticmethod
    def get_summary_by_entry(db: Session, time_entry_id: int) -> List[Tuple[str, int]]:
        query = (
            select(
                TimeEntryAppUsage.application_name,
                func.sum(TimeEntryAppUsage.duration_seconds).label("duration_seconds")
            )
            .where(TimeEntryAppUsage.time_entry_id == time_entry_id)
            .group_by(TimeEntryAppUsage.application_name)
            .order_by(func.sum(TimeEntryAppUsage.duration_seconds).desc())
        )
        results = db.execute(query).all()
        return [(r.application_name, r.duration_seconds) for r in results]

    @staticmethod
    def get_summary_by_filters(
        db: Session,
        organization_id: int,
        user_id: Optional[int] = None,
        project_id: Optional[int] = None,
        task_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        end_before: Optional[datetime] = None
    ) -> List[Tuple[str, int]]:
        """
        Total time per application over a window.

        Two upper bounds, deliberately. `end_date` is **inclusive** and is what
        the web client has always sent (a bare `YYYY-MM-DD`, meaning "up to and
        including that day"); changing it to exclusive would silently drop the
        last day from every existing report. `end_before` is **exclusive** and
        is what a caller asking for one exact calendar day wants: the desktop
        sends `[IST midnight, next IST midnight)`, so the day neither loses its
        final second nor counts a record landing exactly on midnight twice.
        Callers pass one or the other, never both.
        """
        conditions = [TimeEntryAppUsage.organization_id == organization_id]
        
        query = (
            select(
                TimeEntryAppUsage.application_name,
                func.sum(TimeEntryAppUsage.duration_seconds).label("duration_seconds")
            )
            .join(TimeEntry, TimeEntryAppUsage.time_entry_id == TimeEntry.id)
        )
        
        if user_id is not None:
            conditions.append(TimeEntry.user_id == user_id)
        if project_id is not None:
            conditions.append(TimeEntry.project_id == project_id)
        if task_id is not None:
            conditions.append(TimeEntry.task_id == task_id)
        if start_date is not None:
            conditions.append(TimeEntryAppUsage.recorded_at >= start_date)
        if end_date is not None:
            conditions.append(TimeEntryAppUsage.recorded_at <= end_date)
        if end_before is not None:
            conditions.append(TimeEntryAppUsage.recorded_at < end_before)

        query = query.where(and_(*conditions)).group_by(TimeEntryAppUsage.application_name).order_by(func.sum(TimeEntryAppUsage.duration_seconds).desc())
        results = db.execute(query).all()
        return [(r.application_name, r.duration_seconds) for r in results]
