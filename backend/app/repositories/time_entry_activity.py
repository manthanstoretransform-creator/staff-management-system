from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.time_entry_activity import TimeEntryActivity
from app.schemas.time_entry_activity import ActivitySampleCreate


class TimeEntryActivityRepository:
    @staticmethod
    def get_by_client_event_id(db: Session, client_event_id: str) -> Optional[TimeEntryActivity]:
        return db.scalar(
            select(TimeEntryActivity).where(TimeEntryActivity.client_event_id == client_event_id)
        )

    @staticmethod
    def create_batch(
        db: Session,
        organization_id: int,
        time_entry_id: int,
        samples: List[ActivitySampleCreate],
    ) -> List[TimeEntryActivity]:
        """Insert a batch of activity windows, skipping any whose
        client_event_id was already inserted by a previous (retried)
        upload. Commits once for the whole batch."""
        inserted: List[TimeEntryActivity] = []
        for sample in samples:
            if sample.client_event_id and TimeEntryActivityRepository.get_by_client_event_id(
                db, sample.client_event_id
            ):
                continue  # idempotent retry: this window is already stored
            record = TimeEntryActivity(
                organization_id=organization_id,
                time_entry_id=time_entry_id,
                recorded_at=sample.recorded_at,
                keyboard_strokes=sample.keyboard_strokes,
                mouse_clicks=sample.mouse_clicks,
                mouse_movements=sample.mouse_movements,
                activity_percentage=sample.activity_percentage,
                client_event_id=sample.client_event_id,
            )
            db.add(record)
            inserted.append(record)
        db.commit()
        for record in inserted:
            db.refresh(record)
        return inserted
