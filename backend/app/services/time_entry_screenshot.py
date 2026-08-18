from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List, Optional
from app.models.time_entry_screenshot import TimeEntryScreenshot
from app.models.user import User
from app.repositories.time_entry import TimeEntryRepository
from app.repositories.time_entry_screenshot import TimeEntryScreenshotRepository
from app.schemas.time_entry_screenshot import TimeEntryScreenshotCreate

class TimeEntryScreenshotService:
    @staticmethod
    def create_screenshot(
        db: Session,
        payload: TimeEntryScreenshotCreate,
        current_user: User
    ) -> TimeEntryScreenshot:
        # Verify time entry exists and belongs to the user's organization
        time_entry = TimeEntryRepository.get_by_id(db, payload.time_entry_id)
        if not time_entry or time_entry.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time entry not found"
            )
        # If employee, ensure they own the time entry
        if current_user.role_name == "employee" and time_entry.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to add screenshots to this time entry"
            )
        
        return TimeEntryScreenshotRepository.create(
            db=db,
            organization_id=current_user.organization_id,
            time_entry_id=payload.time_entry_id,
            file_path=payload.file_path,
            monitor_number=payload.monitor_number,
            captured_at=payload.captured_at
        )

    @staticmethod
    def list_screenshots(
        db: Session,
        time_entry_id: Optional[int],
        user_id: Optional[int],
        limit: int,
        current_user: User
    ) -> List[TimeEntryScreenshot]:
        # Enforce scoping: employees can only list their own screenshots
        target_user_id = user_id
        if current_user.role_name == "employee":
            target_user_id = current_user.id
            
        return TimeEntryScreenshotRepository.list_screenshots(
            db=db,
            organization_id=current_user.organization_id,
            user_id=target_user_id,
            time_entry_id=time_entry_id,
            limit=limit
        )
