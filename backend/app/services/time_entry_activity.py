from typing import List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.time_entry_activity import TimeEntryActivity
from app.models.user import User
from app.repositories.time_entry import TimeEntryRepository
from app.repositories.time_entry_activity import TimeEntryActivityRepository
from app.schemas.time_entry_activity import ActivityBatchCreate


class TimeEntryActivityService:
    @staticmethod
    def batch_record_activity(
        db: Session,
        time_entry_id: int,
        payload: ActivityBatchCreate,
        current_user: User,
    ) -> Tuple[int, List[TimeEntryActivity]]:
        if not payload.samples:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch request cannot be empty",
            )

        time_entry = TimeEntryRepository.get_by_id(db, time_entry_id)
        if not time_entry or time_entry.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time entry not found",
            )

        if time_entry.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot record activity for another user's time entry",
            )

        # Deliberately no running-status check: the desktop queues windows
        # offline and uploads late, so activity for an entry that has since
        # stopped is expected and must still land.
        inserted = TimeEntryActivityRepository.create_batch(
            db=db,
            organization_id=current_user.organization_id,
            time_entry_id=time_entry_id,
            samples=payload.samples,
        )
        return len(inserted), inserted
