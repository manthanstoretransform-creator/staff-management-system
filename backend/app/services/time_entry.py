from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.core.time_format import elapsed_seconds
from app.repositories.time_entry import TimeEntryRepository
from app.services.task import TaskService

import logging

log = logging.getLogger(__name__)

#: How far in the past a client-supplied event instant may be. The desktop
#: queues start/stop durably and retries with backoff, so a legitimately late
#: sync is normal -- but an unbounded backdate would let a client claim any
#: amount of tracked time, so it is capped rather than trusted outright.
MAX_CLIENT_BACKDATE_SECONDS = 7 * 24 * 3600


class TimeEntryService:
    @staticmethod
    def _event_time(
        client_value: Optional[datetime],
        *,
        label: str,
        not_before: Optional[datetime] = None,
    ) -> datetime:
        """
        Resolve when a timer event actually happened.

        The client's own timestamp is authoritative when it is plausible,
        because the client is where the event occurred; the server clock is
        only a fallback for an absent or unusable value. Without this, a
        queued start or stop was stamped at the moment its retry finally
        reached the API, so an entry that the desktop had been showing as
        (say) 12 minutes long was recorded as 17 minutes -- the extra five
        being the time the request spent waiting in the offline queue.

        Three guards, all of which fall back rather than reject: a naive value
        is read as UTC; a future value is clamped to now (a client clock that
        runs fast must not manufacture time); a value older than
        MAX_CLIENT_BACKDATE_SECONDS, or earlier than `not_before` (the entry's
        own start), is refused.
        """
        now = datetime.now(timezone.utc)
        if client_value is None:
            return now

        value = client_value
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        if value > now:
            log.info("%s from the client is in the future; using the server clock", label)
            return now
        if (now - value).total_seconds() > MAX_CLIENT_BACKDATE_SECONDS:
            log.warning("%s from the client is implausibly old (%s); using the server clock",
                        label, value.isoformat())
            return now
        if not_before is not None:
            reference = not_before if not_before.tzinfo else not_before.replace(tzinfo=timezone.utc)
            if value < reference:
                log.warning("%s from the client precedes the entry's start; using the server clock",
                            label)
                return now
        return value

    @staticmethod
    def start_timer(
        db: Session,
        project_id: int,
        task_id: int,
        description: Optional[str],
        is_billable: Optional[bool],
        current_user: User,
        started_at: Optional[datetime] = None,
    ) -> TimeEntry:
        # 1. Verify project exists in organization and task exists in project
        TaskService.get_task(db, project_id, task_id, current_user)

        # TODO: Add check to ensure user is assigned to the task before logging time once assignee-based restriction is confirmed.

        # 2. Check if user already has an active timer
        active_timer = TimeEntryRepository.get_active_for_user(db, current_user.id)
        if active_timer:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already has an active timer"
            )

        start_time = TimeEntryService._event_time(started_at, label="started_at")

        # 3. Create time entry resolving organization_id from current_user
        return TimeEntryRepository.create(
            db=db,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            project_id=project_id,
            task_id=task_id,
            start_time=start_time,
            is_billable=is_billable if is_billable is not None else False,
            description=description
        )

    @staticmethod
    def stop_timer(
        db: Session,
        entry_id: int,
        description: Optional[str],
        current_user: User,
        stopped_at: Optional[datetime] = None,
    ) -> TimeEntry:
        # 1. Fetch time entry
        time_entry = TimeEntryRepository.get_by_id(db, entry_id)
        
        # 2. Reject with 404 if timer doesn't exist or doesn't belong to the requesting user
        if not time_entry or time_entry.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active timer not found"
            )

        # 3. Reject with 409 if already stopped
        if time_entry.end_time is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Timer is already stopped"
            )

        end_time = TimeEntryService._event_time(
            stopped_at, label="stopped_at", not_before=time_entry.start_time
        )

        # The one canonical duration calculation. Derived from the two
        # timestamps and rounded to the nearest second, so
        # `total_seconds == round(end_time - start_time)` holds for every
        # completed entry and every consumer can re-derive it from the raw
        # columns. It used to be `int(delta.total_seconds())` here, which
        # truncated: a systematic sub-second loss on every single stop.
        total_seconds = elapsed_seconds(time_entry.start_time, end_time)

        log.info(
            "stop entry=%s user=%s start=%s end=%s total_seconds=%s (client stopped_at=%s)",
            time_entry.id, current_user.id,
            time_entry.start_time.isoformat(), end_time.isoformat(),
            total_seconds, stopped_at.isoformat() if stopped_at else None,
        )

        # 3b. Never let a stop silently bank unresolved idle time.
        #
        # A pending idle period means the user was inactive and has not yet
        # answered the popup. Stopping the timer always discards idle time
        # (the "Yes, keep idle time" + "Stop timer" combination discards too),
        # so any period still pending is resolved here as discarded before the
        # end time is written. This stages the idle rows and their deductions;
        # the repository's stop below commits them together with the entry.
        from app.services.time_entry_idle_period import TimeEntryIdlePeriodService

        TimeEntryIdlePeriodService.resolve_pending_for_stop(db, time_entry, end_time)

        # 4. Stop the timer
        stopped_entry = TimeEntryRepository.stop(
            db=db,
            time_entry=time_entry,
            end_time=end_time,
            total_seconds=total_seconds,
            description=description
        )

        # Update the task's time_tracked_seconds
        if stopped_entry.task_id:
            from sqlalchemy import func, select
            from app.models.task import Task

            sum_seconds = db.scalar(
                select(func.sum(TimeEntry.total_seconds))
                .where(
                    TimeEntry.task_id == stopped_entry.task_id,
                    TimeEntry.status.in_(["stopped", "completed"])
                )
            ) or 0

            task = db.scalar(select(Task).where(Task.id == stopped_entry.task_id))
            if task:
                task.time_tracked_seconds = sum_seconds
                db.add(task)
                db.commit()

        return stopped_entry

    @staticmethod
    def list_time_entries(
        db: Session,
        project_id: Optional[int],
        task_id: Optional[int],
        user_id: Optional[int],
        status: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        skip: int,
        limit: int,
        current_user: User
    ) -> Tuple[List[TimeEntry], int]:
        # Enforce user restriction: users without time_entries:view_all permission can only view self
        is_privileged = current_user.permissions.get("time_entries:view_all", False)
        if not is_privileged:
            user_id = current_user.id

        return TimeEntryRepository.list_by_filters(
            db=db,
            organization_id=current_user.organization_id,
            user_id=user_id,
            project_id=project_id,
            task_id=task_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit
        )

    @staticmethod
    def get_time_entry(db: Session, entry_id: int, current_user: User) -> TimeEntry:
        time_entry = TimeEntryRepository.get_by_id(db, entry_id)
        
        # 1. 404 if not found or organization mismatch
        if not time_entry or time_entry.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time entry not found"
            )
            
        # 2. If user lacks time_entries:view_all permission, must belong to self
        is_privileged = current_user.permissions.get("time_entries:view_all", False)
        if not is_privileged and time_entry.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time entry not found"
            )
            
        return time_entry
