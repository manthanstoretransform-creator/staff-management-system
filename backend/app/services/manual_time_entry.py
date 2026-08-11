from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import date, datetime, timezone
from typing import List, Optional, Tuple
from app.models.manual_time_entry import ManualTimeEntry
from app.models.user import User
from app.repositories.manual_time_entry import ManualTimeEntryRepository
from app.services.task import TaskService
from app.schemas.manual_time_entry import ManualTimeEntryCreate

class ManualTimeEntryService:
    @staticmethod
    def create_manual_entry(
        db: Session,
        entry_in: ManualTimeEntryCreate,
        current_user: User
    ) -> ManualTimeEntry:
        # 1. Verify project and task ownership
        TaskService.get_task(db, entry_in.project_id, entry_in.task_id, current_user)

        # 2. work_date cannot be a future date
        today_utc = datetime.now(timezone.utc).date()
        if entry_in.work_date > today_utc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Work date cannot be in the future"
            )

        # 3. total_seconds must be > 0 and <= 86400
        if entry_in.total_seconds <= 0 or entry_in.total_seconds > 86400:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Total seconds must be between 1 and 86400 (24 hours)"
            )

        # 4. Create manual entry
        return ManualTimeEntryRepository.create(
            db=db,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            project_id=entry_in.project_id,
            task_id=entry_in.task_id,
            work_date=entry_in.work_date,
            start_time=entry_in.start_time,
            end_time=entry_in.end_time,
            total_seconds=entry_in.total_seconds,
            description=entry_in.description,
            is_billable=entry_in.is_billable if entry_in.is_billable is not None else True
        )

    @staticmethod
    def list_manual_entries(
        db: Session,
        project_id: Optional[int],
        task_id: Optional[int],
        user_id: Optional[int],
        approval_status: Optional[str],
        start_date: Optional[date],
        end_date: Optional[date],
        skip: int,
        limit: int,
        current_user: User
    ) -> Tuple[List[ManualTimeEntry], int]:
        # Enforce user restriction: users without time_entries:view_all permission can only view self
        is_privileged = current_user.permissions.get("time_entries:view_all", False)
        if not is_privileged:
            user_id = current_user.id

        return ManualTimeEntryRepository.list_by_filters(
            db=db,
            organization_id=current_user.organization_id,
            user_id=user_id,
            project_id=project_id,
            task_id=task_id,
            approval_status=approval_status,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit
        )

    @staticmethod
    def get_manual_entry(db: Session, entry_id: int, current_user: User) -> ManualTimeEntry:
        entry = ManualTimeEntryRepository.get_by_id(db, entry_id)
        
        if not entry or entry.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Manual time entry not found"
            )

        is_privileged = current_user.permissions.get("time_entries:view_all", False)
        if not is_privileged and entry.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Manual time entry not found"
            )

        return entry

    @staticmethod
    def update_approval(
        db: Session,
        entry_id: int,
        approval_status: str,
        current_user: User
    ) -> ManualTimeEntry:
        # TODO: Confirm with senior whether these role-based checks should later be unified into a granular permission-key system.
        is_privileged = current_user.permissions.get("manual_time_entries:approve", False)
        if not is_privileged:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this action"
            )

        entry = ManualTimeEntryRepository.get_by_id(db, entry_id)
        if not entry or entry.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Manual time entry not found"
            )

        if entry.approval_status != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Manual time entry has already been decided"
            )

        return ManualTimeEntryRepository.update_approval_status(
            db=db,
            manual_entry=entry,
            approval_status=approval_status,
            approved_by_user_id=current_user.id,
            approved_at=datetime.now(timezone.utc)
        )
