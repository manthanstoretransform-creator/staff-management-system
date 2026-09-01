from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.time_entry_unwanted_activity import TimeEntryUnwantedActivity


class TimeEntryUnwantedActivityRepository:
    @staticmethod
    def get_by_client_event_id(db: Session, client_event_id: str) -> Optional[TimeEntryUnwantedActivity]:
        return db.scalar(
            select(TimeEntryUnwantedActivity).where(
                TimeEntryUnwantedActivity.client_event_id == client_event_id
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
        activity_type: str,
        key_or_action: str,
        occurrence_count: int,
        alerted: bool,
        alert_count: int,
        recorded_at: Optional[datetime] = None,
        client_event_id: Optional[str] = None,
    ) -> TimeEntryUnwantedActivity:
        record = TimeEntryUnwantedActivity(
            organization_id=organization_id,
            user_id=user_id,
            project_id=project_id,
            task_id=task_id,
            time_entry_id=time_entry_id,
            activity_type=activity_type,
            key_or_action=key_or_action,
            occurrence_count=occurrence_count,
            alerted=alerted,
            alert_count=alert_count,
            recorded_at=recorded_at or datetime.now(timezone.utc),
            client_event_id=client_event_id,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
