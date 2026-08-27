from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func
from typing import List, Optional, Tuple
from datetime import datetime, timezone
from app.models.time_entry_url_usage import TimeEntryUrlUsage
from app.models.time_entry import TimeEntry

class URLUsageRepository:
    @staticmethod
    def get_by_client_event_id(db: Session, client_event_id: str) -> Optional[TimeEntryUrlUsage]:
        return db.scalar(
            select(TimeEntryUrlUsage).where(TimeEntryUrlUsage.client_event_id == client_event_id)
        )

    @staticmethod
    def get_latest_record(
        db: Session,
        organization_id: int,
        time_entry_id: int
    ) -> Optional[TimeEntryUrlUsage]:
        return db.scalar(
            select(TimeEntryUrlUsage)
            .where(
                and_(
                    TimeEntryUrlUsage.organization_id == organization_id,
                    TimeEntryUrlUsage.time_entry_id == time_entry_id
                )
            )
            .order_by(TimeEntryUrlUsage.recorded_at.desc(), TimeEntryUrlUsage.id.desc())
            .limit(1)
        )

    @staticmethod
    def create(
        db: Session,
        organization_id: int,
        time_entry_id: int,
        browser_name: str,
        domain: str,
        url: Optional[str],
        page_title: Optional[str],
        duration_seconds: int,
        recorded_at: Optional[datetime] = None,
        client_event_id: Optional[str] = None
    ) -> TimeEntryUrlUsage:
        now_utc = datetime.now(timezone.utc)
        record = TimeEntryUrlUsage(
            organization_id=organization_id,
            time_entry_id=time_entry_id,
            browser_name=browser_name,
            domain=domain,
            url=url,
            page_title=page_title,
            duration_seconds=duration_seconds,
            recorded_at=recorded_at if recorded_at is not None else now_utc,
            client_event_id=client_event_id
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def update_duration_and_time(
        db: Session,
        record: TimeEntryUrlUsage,
        added_duration: int,
        new_recorded_at: datetime
    ) -> TimeEntryUrlUsage:
        record.duration_seconds += added_duration
        if new_recorded_at > record.recorded_at:
            record.recorded_at = new_recorded_at
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def list_by_filters(
        db: Session,
        organization_id: int,
        user_id: Optional[int] = None,
        time_entry_id: Optional[int] = None,
        domain: Optional[str] = None,
        browser_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
        sort_asc: bool = True
    ) -> Tuple[List[TimeEntryUrlUsage], int]:
        conditions = [TimeEntryUrlUsage.organization_id == organization_id]

        query = select(TimeEntryUrlUsage)

        if user_id is not None:
            query = query.join(TimeEntry, TimeEntryUrlUsage.time_entry_id == TimeEntry.id)
            conditions.append(TimeEntry.user_id == user_id)

        if time_entry_id is not None:
            conditions.append(TimeEntryUrlUsage.time_entry_id == time_entry_id)
        if domain is not None:
            conditions.append(TimeEntryUrlUsage.domain.ilike(f"%{domain}%"))
        if browser_name is not None:
            conditions.append(TimeEntryUrlUsage.browser_name.ilike(f"%{browser_name}%"))
        if start_time is not None:
            conditions.append(TimeEntryUrlUsage.recorded_at >= start_time)
        if end_time is not None:
            conditions.append(TimeEntryUrlUsage.recorded_at <= end_time)

        query = query.where(and_(*conditions))

        count_query = select(func.count()).select_from(query.subquery())
        total = db.scalar(count_query) or 0

        order_clause = TimeEntryUrlUsage.recorded_at.asc() if sort_asc else TimeEntryUrlUsage.recorded_at.desc()
        results = db.scalars(query.order_by(order_clause).offset(skip).limit(limit)).all()
        return list(results), total

    @staticmethod
    def get_domain_summary(
        db: Session,
        organization_id: int,
        time_entry_id: Optional[int] = None,
        user_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Tuple[str, int]]:
        conditions = [TimeEntryUrlUsage.organization_id == organization_id]
        query = select(
            TimeEntryUrlUsage.domain,
            func.sum(TimeEntryUrlUsage.duration_seconds).label("duration_seconds")
        )

        if user_id is not None or time_entry_id is not None:
            query = query.join(TimeEntry, TimeEntryUrlUsage.time_entry_id == TimeEntry.id)
            if user_id is not None:
                conditions.append(TimeEntry.user_id == user_id)

        if time_entry_id is not None:
            conditions.append(TimeEntryUrlUsage.time_entry_id == time_entry_id)
        if start_time is not None:
            conditions.append(TimeEntryUrlUsage.recorded_at >= start_time)
        if end_time is not None:
            conditions.append(TimeEntryUrlUsage.recorded_at <= end_time)

        query = query.where(and_(*conditions)).group_by(TimeEntryUrlUsage.domain).order_by(func.sum(TimeEntryUrlUsage.duration_seconds).desc())
        results = db.execute(query).all()
        return [(r.domain, r.duration_seconds) for r in results]

    @staticmethod
    def get_browser_summary(
        db: Session,
        organization_id: int,
        time_entry_id: Optional[int] = None,
        user_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Tuple[str, int]]:
        conditions = [TimeEntryUrlUsage.organization_id == organization_id]
        query = select(
            TimeEntryUrlUsage.browser_name,
            func.sum(TimeEntryUrlUsage.duration_seconds).label("duration_seconds")
        )

        if user_id is not None or time_entry_id is not None:
            query = query.join(TimeEntry, TimeEntryUrlUsage.time_entry_id == TimeEntry.id)
            if user_id is not None:
                conditions.append(TimeEntry.user_id == user_id)

        if time_entry_id is not None:
            conditions.append(TimeEntryUrlUsage.time_entry_id == time_entry_id)
        if start_time is not None:
            conditions.append(TimeEntryUrlUsage.recorded_at >= start_time)
        if end_time is not None:
            conditions.append(TimeEntryUrlUsage.recorded_at <= end_time)

        query = query.where(and_(*conditions)).group_by(TimeEntryUrlUsage.browser_name).order_by(func.sum(TimeEntryUrlUsage.duration_seconds).desc())
        results = db.execute(query).all()
        return [(r.browser_name, r.duration_seconds) for r in results]
