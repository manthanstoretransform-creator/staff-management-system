from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.time_entry import TimeEntry
from app.models.time_entry_adjustment import TimeEntryAdjustment
from app.models.time_entry_unwanted_activity import TimeEntryUnwantedActivity
from app.models.user import User
from app.repositories.time_entry import TimeEntryRepository
from app.repositories.time_entry_adjustment import TimeEntryAdjustmentRepository
from app.repositories.time_entry_unwanted_activity import TimeEntryUnwantedActivityRepository
from app.schemas.time_entry_adjustment import AdjustmentCreate
from app.schemas.time_entry_unwanted_activity import UnwantedActivityCreate


def _get_owned_entry(db: Session, time_entry_id: int, current_user: User) -> TimeEntry:
    """Fetch a time entry and enforce org + ownership -- the identity/context
    fields (organization/user/project/task) written to both tables come from
    HERE, never from the client, so one user's session can never attribute
    records to another user's time entry."""
    time_entry = TimeEntryRepository.get_by_id(db, time_entry_id)
    if not time_entry or time_entry.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Time entry not found",
        )
    if time_entry.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot record against another user's time entry",
        )
    return time_entry


class TimeEntryUnwantedActivityService:
    @staticmethod
    def record_event(
        db: Session,
        time_entry_id: int,
        payload: UnwantedActivityCreate,
        current_user: User,
    ) -> TimeEntryUnwantedActivity:
        time_entry = _get_owned_entry(db, time_entry_id, current_user)

        if payload.client_event_id:
            existing = TimeEntryUnwantedActivityRepository.get_by_client_event_id(
                db, payload.client_event_id
            )
            if existing:
                return existing  # idempotent retry

        return TimeEntryUnwantedActivityRepository.create(
            db=db,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            project_id=time_entry.project_id,
            task_id=time_entry.task_id,
            time_entry_id=time_entry_id,
            activity_type=payload.activity_type,
            key_or_action=payload.key_or_action,
            occurrence_count=payload.occurrence_count,
            alerted=payload.alerted,
            alert_count=payload.alert_count,
            recorded_at=payload.recorded_at,
            client_event_id=payload.client_event_id,
        )

    @staticmethod
    def record_adjustment(
        db: Session,
        time_entry_id: int,
        payload: AdjustmentCreate,
        current_user: User,
    ) -> TimeEntryAdjustment:
        time_entry = _get_owned_entry(db, time_entry_id, current_user)

        if payload.client_event_id:
            existing = TimeEntryAdjustmentRepository.get_by_client_event_id(
                db, payload.client_event_id
            )
            if existing:
                return existing  # idempotent retry: never deduct twice

        # Link back to the triggering unwanted-activity event, when it has
        # already synced; the two records travel through independent offline
        # queues, so the event may land after the adjustment -- the
        # denormalized source_* fields keep the audit readable either way.
        unwanted_activity_id = None
        if payload.source_client_event_id:
            source = TimeEntryUnwantedActivityRepository.get_by_client_event_id(
                db, payload.source_client_event_id
            )
            if source and source.time_entry_id == time_entry_id:
                unwanted_activity_id = source.id

        return TimeEntryAdjustmentRepository.create(
            db=db,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            project_id=time_entry.project_id,
            task_id=time_entry.task_id,
            time_entry_id=time_entry_id,
            adjustment_seconds=payload.adjustment_seconds,
            reason=payload.reason,
            source_activity_type=payload.source_activity_type,
            source_key_or_action=payload.source_key_or_action,
            unwanted_activity_id=unwanted_activity_id,
            recorded_at=payload.recorded_at,
            client_event_id=payload.client_event_id,
        )
