from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List, Optional
from app.models.time_entry_screenshot import TimeEntryScreenshot

class TimeEntryScreenshotRepository:
    @staticmethod
    def create(
        db: Session,
        organization_id: int,
        time_entry_id: int,
        file_path: str,
        monitor_number: int,
        captured_at: Optional[datetime] = None
    ) -> TimeEntryScreenshot:
        screenshot = TimeEntryScreenshot(
            organization_id=organization_id,
            time_entry_id=time_entry_id,
            file_path=file_path,
            monitor_number=monitor_number,
            captured_at=captured_at if captured_at is not None else datetime.now(timezone.utc)
        )
        db.add(screenshot)
        db.commit()
        db.refresh(screenshot)
        return screenshot

    @staticmethod
    def get_by_id(db: Session, screenshot_id: int) -> Optional[TimeEntryScreenshot]:
        return db.query(TimeEntryScreenshot).filter(TimeEntryScreenshot.id == screenshot_id).first()

    @staticmethod
    def list_screenshots(
        db: Session,
        organization_id: int,
        user_id: Optional[int] = None,
        time_entry_id: Optional[int] = None,
        limit: int = 100
    ) -> List[TimeEntryScreenshot]:
        query = db.query(TimeEntryScreenshot).filter(TimeEntryScreenshot.organization_id == organization_id)
        if time_entry_id is not None:
            query = query.filter(TimeEntryScreenshot.time_entry_id == time_entry_id)
        if user_id is not None:
            from app.models.time_entry import TimeEntry
            query = query.join(TimeEntry).filter(TimeEntry.user_id == user_id)
            
        return query.order_by(TimeEntryScreenshot.captured_at.desc()).limit(limit).all()
