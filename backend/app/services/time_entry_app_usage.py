from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
from app.models.user import User
from app.models.time_entry_app_usage import TimeEntryAppUsage
from app.repositories.time_entry_app_usage import TimeEntryAppUsageRepository
from app.repositories.time_entry import TimeEntryRepository
from app.schemas.time_entry_app_usage import AppUsageCreate, AppUsageBatchCreate

class TimeEntryAppUsageService:
    @staticmethod
    def record_usage(
        db: Session,
        time_entry_id: int,
        payload: AppUsageCreate,
        current_user: User
    ) -> TimeEntryAppUsage:
        # 1. Fetch and validate time entry
        time_entry = TimeEntryRepository.get_by_id(db, time_entry_id)
        if not time_entry or time_entry.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time entry not found"
            )

        # 2. Check ownership
        if time_entry.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot record app usage for another user's time entry"
            )

        # 3. Check if time entry is active
        if time_entry.end_time is not None or time_entry.status != 'running':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot record app usage for a stopped time entry"
            )

        return TimeEntryAppUsageRepository.create(
            db=db,
            organization_id=current_user.organization_id,
            time_entry_id=time_entry_id,
            application_name=payload.application_name,
            window_title=payload.window_title,
            duration_seconds=payload.duration_seconds,
            recorded_at=payload.recorded_at
        )

    @staticmethod
    def batch_record_usage(
        db: Session,
        time_entry_id: int,
        payload: AppUsageBatchCreate,
        current_user: User
    ) -> Tuple[int, List[TimeEntryAppUsage]]:
        # 1. Validate non-empty batch
        if not payload.records:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch request cannot be empty"
            )

        # 2. Fetch and validate time entry
        time_entry = TimeEntryRepository.get_by_id(db, time_entry_id)
        if not time_entry or time_entry.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time entry not found"
            )

        # 3. Check ownership
        if time_entry.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot record app usage for another user's time entry"
            )

        # 4. Check if time entry is active
        if time_entry.end_time is not None or time_entry.status != 'running':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot record app usage for a stopped time entry"
            )

        inserted = TimeEntryAppUsageRepository.create_batch(
            db=db,
            organization_id=current_user.organization_id,
            time_entry_id=time_entry_id,
            records=payload.records
        )
        return len(inserted), inserted

    @staticmethod
    def list_usage(
        db: Session,
        time_entry_id: int,
        application_name: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        skip: int,
        limit: int,
        current_user: User
    ) -> Tuple[List[TimeEntryAppUsage], int]:
        # 1. Fetch time entry
        time_entry = TimeEntryRepository.get_by_id(db, time_entry_id)
        if not time_entry or time_entry.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time entry not found"
            )

        # 2. Enforce role-based scoping
        is_privileged = current_user.permissions.get("time_entries:view_all", False)
        if not is_privileged and time_entry.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time entry not found"
            )

        return TimeEntryAppUsageRepository.list_by_filters(
            db=db,
            organization_id=current_user.organization_id,
            time_entry_id=time_entry_id,
            application_name=application_name,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit
        )

    @staticmethod
    def get_summary(
        db: Session,
        time_entry_id: int,
        current_user: User
    ) -> Tuple[int, List[Dict[str, Any]]]:
        # 1. Fetch time entry
        time_entry = TimeEntryRepository.get_by_id(db, time_entry_id)
        if not time_entry or time_entry.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time entry not found"
            )

        # 2. Enforce role-based scoping
        is_privileged = current_user.permissions.get("time_entries:view_all", False)
        if not is_privileged and time_entry.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time entry not found"
            )

        raw_summary = TimeEntryAppUsageRepository.get_summary_by_entry(db, time_entry_id)
        total_seconds = sum(duration for _, duration in raw_summary)

        applications = []
        for app_name, duration in raw_summary:
            percentage = round((duration / total_seconds) * 100, 2) if total_seconds > 0 else 0.0
            applications.append({
                "application_name": app_name,
                "duration_seconds": duration,
                "percentage": percentage
            })

        return total_seconds, applications

    @staticmethod
    def list_usage_global(
        db: Session,
        user_id: Optional[int],
        time_entry_id: Optional[int],
        application_name: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        skip: int,
        limit: int,
        current_user: User
    ) -> Tuple[List[TimeEntryAppUsage], int]:
        # Enforce employee restriction: non-privileged users can only view self
        is_privileged = current_user.permissions.get("time_entries:view_all", False)
        if not is_privileged:
            user_id = current_user.id

        return TimeEntryAppUsageRepository.list_by_filters(
            db=db,
            organization_id=current_user.organization_id,
            user_id=user_id,
            time_entry_id=time_entry_id,
            application_name=application_name,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit
        )

    @staticmethod
    def get_summary_global(
        db: Session,
        user_id: Optional[int],
        project_id: Optional[int],
        task_id: Optional[int],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        current_user: User
    ) -> Tuple[int, List[Dict[str, Any]]]:
        # Enforce employee restriction: non-privileged users can only view self
        is_privileged = current_user.permissions.get("time_entries:view_all", False)
        if not is_privileged:
            user_id = current_user.id

        raw_summary = TimeEntryAppUsageRepository.get_summary_by_filters(
            db=db,
            organization_id=current_user.organization_id,
            user_id=user_id,
            project_id=project_id,
            task_id=task_id,
            start_date=start_date,
            end_date=end_date
        )
        total_seconds = sum(duration for _, duration in raw_summary)

        applications = []
        for app_name, duration in raw_summary:
            percentage = round((duration / total_seconds) * 100, 2) if total_seconds > 0 else 0.0
            applications.append({
                "application_name": app_name,
                "duration_seconds": duration,
                "percentage": percentage
            })

        return total_seconds, applications
