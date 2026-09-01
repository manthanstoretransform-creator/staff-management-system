from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.time_entry_adjustment import TimeEntryAdjustment


class TimeEntryAdjustmentRepository:
    @staticmethod
    def get_by_client_event_id(db: Session, client_event_id: str) -> Optional[TimeEntryAdjustment]:
        return db.scalar(
            select(TimeEntryAdjustment).where(
                TimeEntryAdjustment.client_event_id == client_event_id
            )
        )

    @staticmethod
    def create(
        db: Session,
        organization_id: int,
        user_id: int,
        project_id: int,
        task_id: int,
        time_entry_id: int,
        adjustment_seconds: int,
        reason: str,
        source_activity_type: Optional[str] = None,
        source_key_or_action: Optional[str] = None,
        unwanted_activity_id: Optional[int] = None,
        recorded_at: Optional[datetime] = None,
        client_event_id: Optional[str] = None,
    ) -> TimeEntryAdjustment:
        record = TimeEntryAdjustment(
            organization_id=organization_id,
            user_id=user_id,
            project_id=project_id,
            task_id=task_id,
            time_entry_id=time_entry_id,
            adjustment_seconds=adjustment_seconds,
            reason=reason,
            source_activity_type=source_activity_type,
            source_key_or_action=source_key_or_action,
            unwanted_activity_id=unwanted_activity_id,
            recorded_at=recorded_at or datetime.now(timezone.utc),
            client_event_id=client_event_id,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def sum_for_entry(db: Session, time_entry_id: int) -> int:
        """Total signed adjustment seconds for one time entry (0 if none)."""
        return int(
            db.scalar(
                select(func.coalesce(func.sum(TimeEntryAdjustment.adjustment_seconds), 0)).where(
                    TimeEntryAdjustment.time_entry_id == time_entry_id
                )
            )
            or 0
        )
