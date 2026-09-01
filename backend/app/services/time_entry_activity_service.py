from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, date

from app.models.user import User
from app.models.time_entry import TimeEntry
from app.schemas.time_entry_activity import (
    TimeEntryActivityCreate, TimeEntryActivityBatchCreate, TimeEntryActivityUpdate
)
from app.repositories.time_entry_activity_repository import TimeEntryActivityRepository


# Configurable Thresholds & Weights
MAX_KEYBOARD_STROKES_PER_INTERVAL = 120
MAX_MOUSE_CLICKS_PER_INTERVAL = 30
MAX_MOUSE_MOVEMENTS_PER_INTERVAL = 400

KEYBOARD_WEIGHT = 0.40
MOUSE_CLICK_WEIGHT = 0.30
MOUSE_MOVEMENT_WEIGHT = 0.30


def calculate_activity_percentage(
    keyboard_strokes: int,
    mouse_clicks: int,
    mouse_movements: int
) -> int:
    """Calculate normalized activity percentage (0-100) from counters."""
    k_score = min(max(0, keyboard_strokes) / MAX_KEYBOARD_STROKES_PER_INTERVAL, 1.0)
    c_score = min(max(0, mouse_clicks) / MAX_MOUSE_CLICKS_PER_INTERVAL, 1.0)
    m_score = min(max(0, mouse_movements) / MAX_MOUSE_MOVEMENTS_PER_INTERVAL, 1.0)

    total_score = (
        k_score * KEYBOARD_WEIGHT
        + c_score * MOUSE_CLICK_WEIGHT
        + m_score * MOUSE_MOVEMENT_WEIGHT
    )
    percentage = round(total_score * 100)
    return max(0, min(100, percentage))


class TimeEntryActivityService:
    @staticmethod
    def _verify_time_entry_ownership(
        db: Session,
        time_entry_id: int,
        organization_id: int,
        current_user: User
    ) -> TimeEntry:
        entry = db.scalar(
            select_query := TimeEntryActivityRepository.get_by_id(db, -1)  # dummy to get session access
        ) if False else db.scalar(
            TimeEntry.__table__.select().where(TimeEntry.id == time_entry_id)
        )
        entry_obj = db.get(TimeEntry, time_entry_id)
        if not entry_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Time entry {time_entry_id} not found"
            )
        if entry_obj.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Time entry does not belong to the specified organization"
            )
        if current_user.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not belong to the target organization"
            )
        return entry_obj

    @staticmethod
    def record_activity(
        db: Session,
        payload: TimeEntryActivityCreate,
        current_user: User
    ):
        TimeEntryActivityService._verify_time_entry_ownership(
            db, payload.time_entry_id, payload.organization_id, current_user
        )

        # If activity_percentage is 0 but counters are present, compute it automatically
        act_pct = payload.activity_percentage
        if act_pct == 0 and (payload.keyboard_strokes > 0 or payload.mouse_clicks > 0 or payload.mouse_movements > 0):
            act_pct = calculate_activity_percentage(
                payload.keyboard_strokes, payload.mouse_clicks, payload.mouse_movements
            )

        return TimeEntryActivityRepository.create(
            db=db,
            organization_id=payload.organization_id,
            time_entry_id=payload.time_entry_id,
            recorded_at=payload.recorded_at,
            keyboard_strokes=payload.keyboard_strokes,
            mouse_clicks=payload.mouse_clicks,
            mouse_movements=payload.mouse_movements,
            activity_percentage=act_pct
        )

    @staticmethod
    def batch_record_activity(
        db: Session,
        payload: TimeEntryActivityBatchCreate,
        current_user: User
    ) -> Tuple[int, int]:
        valid_items = []
        failed_count = 0

        for item in payload.activities:
            try:
                if item.organization_id != current_user.organization_id:
                    failed_count += 1
                    continue
                
                act_pct = item.activity_percentage
                if act_pct == 0 and (item.keyboard_strokes > 0 or item.mouse_clicks > 0 or item.mouse_movements > 0):
                    act_pct = calculate_activity_percentage(
                        item.keyboard_strokes, item.mouse_clicks, item.mouse_movements
                    )

                valid_items.append({
                    "organization_id": item.organization_id,
                    "time_entry_id": item.time_entry_id,
                    "recorded_at": item.recorded_at,
                    "keyboard_strokes": item.keyboard_strokes,
                    "mouse_clicks": item.mouse_clicks,
                    "mouse_movements": item.mouse_movements,
                    "activity_percentage": act_pct
                })
            except Exception:
                failed_count += 1

        accepted, repo_failed = TimeEntryActivityRepository.create_batch(db, valid_items)
        return accepted, failed_count + repo_failed

    @staticmethod
    def get_activity_by_id(
        db: Session,
        activity_id: int,
        current_user: User
    ):
        record = TimeEntryActivityRepository.get_by_id(db, activity_id, current_user.organization_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Activity record {activity_id} not found"
            )
        return record

    @staticmethod
    def update_activity(
        db: Session,
        activity_id: int,
        payload: TimeEntryActivityUpdate,
        current_user: User
    ):
        record = TimeEntryActivityService.get_activity_by_id(db, activity_id, current_user)
        return TimeEntryActivityRepository.update(
            db=db,
            record=record,
            keyboard_strokes=payload.keyboard_strokes,
            mouse_clicks=payload.mouse_clicks,
            mouse_movements=payload.mouse_movements,
            activity_percentage=payload.activity_percentage
        )

    @staticmethod
    def delete_activity(
        db: Session,
        activity_id: int,
        current_user: User
    ):
        record = TimeEntryActivityService.get_activity_by_id(db, activity_id, current_user)
        TimeEntryActivityRepository.delete(db, record)

    @staticmethod
    def list_activities(
        db: Session,
        current_user: User,
        user_id: Optional[int] = None,
        time_entry_id: Optional[int] = None,
        project_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100
    ):
        return TimeEntryActivityRepository.list_by_filters(
            db=db,
            organization_id=current_user.organization_id,
            user_id=user_id,
            time_entry_id=time_entry_id,
            project_id=project_id,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit
        )

    @staticmethod
    def get_overview(
        db: Session,
        current_user: User,
        user_id: Optional[int] = None,
        time_entry_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ):
        return TimeEntryActivityRepository.get_overview(
            db=db,
            organization_id=current_user.organization_id,
            user_id=user_id,
            time_entry_id=time_entry_id,
            start_date=start_date,
            end_date=end_date
        )

    @staticmethod
    def get_timeline(
        db: Session,
        current_user: User,
        user_id: Optional[int] = None,
        time_entry_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ):
        return TimeEntryActivityRepository.get_timeline(
            db=db,
            organization_id=current_user.organization_id,
            user_id=user_id,
            time_entry_id=time_entry_id,
            start_date=start_date,
            end_date=end_date
        )

    @staticmethod
    def get_hourly(
        db: Session,
        current_user: User,
        user_id: Optional[int] = None,
        time_entry_id: Optional[int] = None,
        target_date: Optional[date] = None
    ):
        return TimeEntryActivityRepository.get_hourly(
            db=db,
            organization_id=current_user.organization_id,
            user_id=user_id,
            time_entry_id=time_entry_id,
            target_date=target_date
        )
