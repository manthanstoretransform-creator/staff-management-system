from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func
from typing import List, Optional, Tuple
from datetime import date, datetime
from app.models.manual_time_entry import ManualTimeEntry

class ManualTimeEntryRepository:
    @staticmethod
    def get_by_id(db: Session, entry_id: int) -> Optional[ManualTimeEntry]:
        return db.get(ManualTimeEntry, entry_id)

    @staticmethod
    def create(
        db: Session,
        organization_id: int,
        user_id: int,
        project_id: int,
        task_id: int,
        work_date: date,
        start_time: datetime,
        end_time: datetime,
        total_seconds: int,
        description: Optional[str] = None,
        is_billable: bool = True
    ) -> ManualTimeEntry:
        db_entry = ManualTimeEntry(
            organization_id=organization_id,
            user_id=user_id,
            project_id=project_id,
            task_id=task_id,
            work_date=work_date,
            start_time=start_time,
            end_time=end_time,
            total_seconds=total_seconds,
            description=description,
            is_billable=is_billable,
            approval_status='pending'
        )
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
        return db_entry

    @staticmethod
    def update_approval_status(
        db: Session,
        manual_entry: ManualTimeEntry,
        approval_status: str,
        approved_by_user_id: int,
        approved_at: datetime
    ) -> ManualTimeEntry:
        manual_entry.approval_status = approval_status
        manual_entry.approved_by = approved_by_user_id
        manual_entry.approved_at = approved_at
        db.commit()
        db.refresh(manual_entry)
        return manual_entry

    @staticmethod
    def list_by_filters(
        db: Session,
        organization_id: int,
        user_id: Optional[int] = None,
        project_id: Optional[int] = None,
        task_id: Optional[int] = None,
        approval_status: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[ManualTimeEntry], int]:
        conditions = [ManualTimeEntry.organization_id == organization_id]
        
        if user_id is not None:
            conditions.append(ManualTimeEntry.user_id == user_id)
        if project_id is not None:
            conditions.append(ManualTimeEntry.project_id == project_id)
        if task_id is not None:
            conditions.append(ManualTimeEntry.task_id == task_id)
        if approval_status is not None:
            conditions.append(ManualTimeEntry.approval_status == approval_status)
        if start_date is not None:
            conditions.append(ManualTimeEntry.work_date >= start_date)
        if end_date is not None:
            conditions.append(ManualTimeEntry.work_date <= end_date)

        query = select(ManualTimeEntry).where(and_(*conditions))
        
        count = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        
        results = db.scalars(query.order_by(ManualTimeEntry.work_date.desc()).offset(skip).limit(limit)).all()
        return list(results), count
