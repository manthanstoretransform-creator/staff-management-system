from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func
from typing import List, Optional, Tuple
from datetime import datetime
from app.models.time_entry import TimeEntry

class TimeEntryRepository:
    @staticmethod
    def get_by_id(db: Session, entry_id: int) -> Optional[TimeEntry]:
        return db.get(TimeEntry, entry_id)

    @staticmethod
    def get_active_for_user(db: Session, user_id: int) -> Optional[TimeEntry]:
        return db.scalar(
            select(TimeEntry).where(
                TimeEntry.user_id == user_id,
                TimeEntry.end_time.is_(None)
            )
        )

    @staticmethod
    def create(
        db: Session,
        organization_id: int,
        user_id: int,
        project_id: int,
        task_id: int,
        start_time: datetime,
        is_billable: bool = False,
        description: Optional[str] = None
    ) -> TimeEntry:
        db_entry = TimeEntry(
            organization_id=organization_id,
            user_id=user_id,
            project_id=project_id,
            task_id=task_id,
            start_time=start_time,
            status='running',
            is_manual=False,
            is_billable=is_billable,
            description=description
        )
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
        return db_entry

    @staticmethod
    def stop(
        db: Session,
        time_entry: TimeEntry,
        end_time: datetime,
        total_seconds: int,
        description: Optional[str] = None
    ) -> TimeEntry:
        time_entry.end_time = end_time
        time_entry.total_seconds = total_seconds
        time_entry.status = 'stopped'
        if description is not None:
            time_entry.description = description
        db.commit()
        db.refresh(time_entry)
        return time_entry

    @staticmethod
    def list_by_filters(
        db: Session,
        organization_id: int,
        user_id: Optional[int] = None,
        project_id: Optional[int] = None,
        task_id: Optional[int] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[TimeEntry], int]:
        conditions = [TimeEntry.organization_id == organization_id]
        
        if user_id is not None:
            conditions.append(TimeEntry.user_id == user_id)
        if project_id is not None:
            conditions.append(TimeEntry.project_id == project_id)
        if task_id is not None:
            conditions.append(TimeEntry.task_id == task_id)
        if status is not None:
            conditions.append(TimeEntry.status == status)
        if start_date is not None:
            conditions.append(TimeEntry.start_time >= start_date)
        if end_date is not None:
            conditions.append(TimeEntry.start_time <= end_date)

        query = select(TimeEntry).where(and_(*conditions))
        
        count = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        
        results = db.scalars(query.order_by(TimeEntry.start_time.desc()).offset(skip).limit(limit)).all()
        return list(results), count
