from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.repositories.time_entry import TimeEntryRepository
from app.services.task import TaskService

class TimeEntryService:
    @staticmethod
    def start_timer(
        db: Session,
        project_id: int,
        task_id: int,
        description: Optional[str],
        is_billable: Optional[bool],
        current_user: User
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

        start_time = datetime.now(timezone.utc)
        
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
        current_user: User
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

        end_time = datetime.now(timezone.utc)
        
        # Calculate duration in seconds
        delta = end_time - time_entry.start_time
        total_seconds = max(0, int(delta.total_seconds()))

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
