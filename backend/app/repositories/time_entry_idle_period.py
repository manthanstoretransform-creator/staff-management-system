from datetime import datetime
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.time_entry_idle_period import IdlePeriodStatus, TimeEntryIdlePeriod


class TimeEntryIdlePeriodRepository:
    """Data access for idle periods.

    Unlike the older repositories in this package these methods FLUSH rather
    than COMMIT. An idle resolution or reassignment touches three tables
    (`time_entry_idle_periods`, `time_entry_adjustments`, `time_entries`) and
    must land all-or-nothing, so the single commit belongs to the service that
    owns the whole operation.
    """

    @staticmethod
    def get_by_id(db: Session, idle_period_id: int) -> Optional[TimeEntryIdlePeriod]:
        return db.get(TimeEntryIdlePeriod, idle_period_id)

    @staticmethod
    def get_for_update(db: Session, idle_period_id: int) -> Optional[TimeEntryIdlePeriod]:
        """Fetch one idle period with a row lock held for the rest of the
        transaction. This is what makes a double-clicked Resume safe: the
        second request blocks until the first has committed, then sees
        `status = 'resolved'` instead of racing it."""
        return db.scalar(
            select(TimeEntryIdlePeriod)
            .where(TimeEntryIdlePeriod.id == idle_period_id)
            .with_for_update()
        )

    @staticmethod
    def get_by_client_event_id(db: Session, client_event_id: str) -> Optional[TimeEntryIdlePeriod]:
        return db.scalar(
            select(TimeEntryIdlePeriod).where(
                TimeEntryIdlePeriod.client_event_id == client_event_id
            )
        )

    @staticmethod
    def get_pending_for_entry(db: Session, time_entry_id: int) -> Optional[TimeEntryIdlePeriod]:
        return db.scalar(
            select(TimeEntryIdlePeriod).where(
                TimeEntryIdlePeriod.time_entry_id == time_entry_id,
                TimeEntryIdlePeriod.status == IdlePeriodStatus.PENDING,
            )
        )

    @staticmethod
    def list_pending_for_entry(db: Session, time_entry_id: int) -> List[TimeEntryIdlePeriod]:
        """Every unresolved idle period on one entry, locked.

        The partial unique index allows only one, but the stop path reads this
        as a list so a historical row that predates the index (or one left by
        a partially applied migration) is still resolved rather than silently
        counted.
        """
        return list(
            db.scalars(
                select(TimeEntryIdlePeriod)
                .where(
                    TimeEntryIdlePeriod.time_entry_id == time_entry_id,
                    TimeEntryIdlePeriod.status == IdlePeriodStatus.PENDING,
                )
                .order_by(TimeEntryIdlePeriod.idle_started_at, TimeEntryIdlePeriod.id)
                .with_for_update()
            ).all()
        )

    @staticmethod
    def list_for_entry(db: Session, time_entry_id: int) -> List[TimeEntryIdlePeriod]:
        return list(
            db.scalars(
                select(TimeEntryIdlePeriod)
                .where(TimeEntryIdlePeriod.time_entry_id == time_entry_id)
                .order_by(TimeEntryIdlePeriod.idle_started_at, TimeEntryIdlePeriod.id)
            ).all()
        )

    @staticmethod
    def create(
        db: Session,
        organization_id: int,
        user_id: int,
        time_entry_id: int,
        original_project_id: int,
        original_task_id: int,
        idle_started_at: datetime,
        idle_detected_at: datetime,
        client_event_id: Optional[str] = None,
    ) -> TimeEntryIdlePeriod:
        record = TimeEntryIdlePeriod(
            organization_id=organization_id,
            user_id=user_id,
            time_entry_id=time_entry_id,
            original_project_id=original_project_id,
            original_task_id=original_task_id,
            idle_started_at=idle_started_at,
            idle_detected_at=idle_detected_at,
            status=IdlePeriodStatus.PENDING,
            reassigned=False,
            client_event_id=client_event_id,
        )
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def mark_resolved(
        db: Session,
        idle_period: TimeEntryIdlePeriod,
        resolved_at: datetime,
        idle_duration_seconds: int,
        keep_idle_time: bool,
        action: str,
        counted: bool,
    ) -> TimeEntryIdlePeriod:
        idle_period.resolved_at = resolved_at
        idle_period.idle_duration_seconds = idle_duration_seconds
        idle_period.keep_idle_time = keep_idle_time
        idle_period.action = action
        idle_period.counted = counted
        idle_period.status = IdlePeriodStatus.RESOLVED
        db.add(idle_period)
        db.flush()
        return idle_period

    @staticmethod
    def mark_reassigned(
        db: Session,
        idle_period: TimeEntryIdlePeriod,
        reassigned_at: datetime,
        project_id: int,
        task_id: int,
        reassigned_time_entry_id: int,
        reassigned_seconds: int,
    ) -> TimeEntryIdlePeriod:
        idle_period.reassigned = True
        idle_period.reassigned_at = reassigned_at
        idle_period.reassigned_project_id = project_id
        idle_period.reassigned_task_id = task_id
        idle_period.reassigned_time_entry_id = reassigned_time_entry_id
        idle_period.reassigned_seconds = reassigned_seconds
        db.add(idle_period)
        db.flush()
        return idle_period

    @staticmethod
    def sum_reassigned_seconds_for_entry(db: Session, time_entry_id: int) -> int:
        return int(
            db.scalar(
                select(
                    func.coalesce(func.sum(TimeEntryIdlePeriod.reassigned_seconds), 0)
                ).where(
                    TimeEntryIdlePeriod.time_entry_id == time_entry_id,
                    TimeEntryIdlePeriod.reassigned.is_(True),
                )
            )
            or 0
        )
