from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse
from app.models.user import User
from app.models.time_entry_url_usage import TimeEntryUrlUsage
from app.repositories.url_usage_repository import URLUsageRepository
from app.repositories.time_entry import TimeEntryRepository
from app.schemas.url_usage import URLUsageCreate, URLUsageBatchCreate

AGGREGATION_WINDOW_SECONDS = 300  # 5 minutes window for merging consecutive identical URL sessions

def normalize_url(url_str: Optional[str], domain_fallback: str) -> Tuple[str, Optional[str]]:
    """
    Normalizes domain and URL string.
    - Domain: lowercased, stripped.
    - URL: scheme and netloc lowercased, trailing slashes removed safely from non-root paths.
    """
    clean_domain = domain_fallback.strip().lower() if domain_fallback else ""

    if not url_str or not url_str.strip():
        return clean_domain, None

    url_clean = url_str.strip()
    try:
        parsed = urlparse(url_clean)
        if not parsed.scheme or not parsed.netloc:
            # Handle URLs without scheme, e.g. "github.com/project"
            parsed = urlparse(f"https://{url_clean}")

        netloc = parsed.netloc.lower()
        # Extract hostname without port for domain if domain_fallback was generic
        extracted_domain = parsed.hostname.lower() if parsed.hostname else clean_domain
        if extracted_domain:
            clean_domain = extracted_domain

        path = parsed.path
        if len(path) > 1 and path.endswith('/'):
            path = path.rstrip('/')

        normalized_url = urlunparse((
            parsed.scheme.lower(),
            netloc,
            path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        return clean_domain, normalized_url
    except Exception:
        return clean_domain, url_clean


class URLUsageService:
    @staticmethod
    def _validate_time_entry_for_write(db: Session, time_entry_id: int, current_user: User):
        time_entry = TimeEntryRepository.get_by_id(db, time_entry_id)
        if not time_entry or time_entry.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time entry not found"
            )
        if time_entry.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot record URL usage for another user's time entry"
            )
        if time_entry.end_time is not None or time_entry.status != 'running':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot record URL usage for a stopped time entry"
            )
        return time_entry

    @staticmethod
    def record_usage(
        db: Session,
        payload: URLUsageCreate,
        current_user: User
    ) -> TimeEntryUrlUsage:
        # 1. Validate time entry & authorization
        URLUsageService._validate_time_entry_for_write(db, payload.time_entry_id, current_user)

        # 2. Check idempotency if client_event_id provided
        if payload.client_event_id:
            existing = URLUsageRepository.get_by_client_event_id(db, payload.client_event_id)
            if existing:
                return existing

        # 3. Normalize domain and URL
        norm_domain, norm_url = normalize_url(payload.url, payload.domain)
        recorded_at = payload.recorded_at if payload.recorded_at is not None else datetime.now(timezone.utc)

        # 4. Consecutive same URL aggregation logic
        latest = URLUsageRepository.get_latest_record(
            db=db,
            organization_id=current_user.organization_id,
            time_entry_id=payload.time_entry_id
        )

        if (
            latest is not None and
            latest.browser_name == payload.browser_name.strip() and
            latest.domain == norm_domain and
            (latest.url or None) == norm_url and
            abs((recorded_at - latest.recorded_at).total_seconds()) <= AGGREGATION_WINDOW_SECONDS
        ):
            return URLUsageRepository.update_duration_and_time(
                db=db,
                record=latest,
                added_duration=payload.duration_seconds,
                new_recorded_at=recorded_at
            )

        # 5. Create new record
        return URLUsageRepository.create(
            db=db,
            organization_id=current_user.organization_id,
            time_entry_id=payload.time_entry_id,
            browser_name=payload.browser_name.strip(),
            domain=norm_domain,
            url=norm_url,
            page_title=payload.page_title.strip() if payload.page_title else None,
            duration_seconds=payload.duration_seconds,
            recorded_at=recorded_at,
            client_event_id=payload.client_event_id
        )

    @staticmethod
    def batch_record_usage(
        db: Session,
        payload: URLUsageBatchCreate,
        current_user: User
    ) -> Tuple[int, int]:
        if not payload.records:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch request cannot be empty"
            )

        validated_time_entries: Dict[int, Any] = {}
        accepted_count = 0
        failed_count = 0

        for r in payload.records:
            if r.time_entry_id not in validated_time_entries:
                time_entry = URLUsageService._validate_time_entry_for_write(db, r.time_entry_id, current_user)
                validated_time_entries[r.time_entry_id] = time_entry

            # Idempotency check
            if r.client_event_id:
                existing = URLUsageRepository.get_by_client_event_id(db, r.client_event_id)
                if existing:
                    accepted_count += 1
                    continue

            norm_domain, norm_url = normalize_url(r.url, r.domain)
            recorded_at = r.recorded_at if r.recorded_at is not None else datetime.now(timezone.utc)

            latest = URLUsageRepository.get_latest_record(
                db=db,
                organization_id=current_user.organization_id,
                time_entry_id=r.time_entry_id
            )

            if (
                latest is not None and
                latest.browser_name == r.browser_name.strip() and
                latest.domain == norm_domain and
                (latest.url or None) == norm_url and
                abs((recorded_at - latest.recorded_at).total_seconds()) <= AGGREGATION_WINDOW_SECONDS
            ):
                URLUsageRepository.update_duration_and_time(
                    db=db,
                    record=latest,
                    added_duration=r.duration_seconds,
                    new_recorded_at=recorded_at
                )
            else:
                URLUsageRepository.create(
                    db=db,
                    organization_id=current_user.organization_id,
                    time_entry_id=r.time_entry_id,
                    browser_name=r.browser_name.strip(),
                    domain=norm_domain,
                    url=norm_url,
                    page_title=r.page_title.strip() if r.page_title else None,
                    duration_seconds=r.duration_seconds,
                    recorded_at=recorded_at,
                    client_event_id=r.client_event_id
                )
            accepted_count += 1

        return accepted_count, failed_count

    @staticmethod
    def list_usage_for_entry(
        db: Session,
        time_entry_id: int,
        domain: Optional[str],
        browser_name: Optional[str],
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        skip: int,
        limit: int,
        current_user: User
    ) -> Tuple[List[TimeEntryUrlUsage], int]:
        time_entry = TimeEntryRepository.get_by_id(db, time_entry_id)
        if not time_entry or time_entry.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time entry not found"
            )

        is_privileged = current_user.permissions.get("time_entries:view_all", False)
        if not is_privileged and time_entry.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time entry not found"
            )

        return URLUsageRepository.list_by_filters(
            db=db,
            organization_id=current_user.organization_id,
            time_entry_id=time_entry_id,
            domain=domain,
            browser_name=browser_name,
            start_time=start_time,
            end_time=end_time,
            skip=skip,
            limit=limit,
            sort_asc=True
        )

    @staticmethod
    def get_summary_for_entry(
        db: Session,
        time_entry_id: int,
        current_user: User
    ) -> Dict[str, Any]:
        time_entry = TimeEntryRepository.get_by_id(db, time_entry_id)
        if not time_entry or time_entry.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time entry not found"
            )

        is_privileged = current_user.permissions.get("time_entries:view_all", False)
        if not is_privileged and time_entry.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time entry not found"
            )

        domain_rows = URLUsageRepository.get_domain_summary(
            db=db,
            organization_id=current_user.organization_id,
            time_entry_id=time_entry_id
        )
        browser_rows = URLUsageRepository.get_browser_summary(
            db=db,
            organization_id=current_user.organization_id,
            time_entry_id=time_entry_id
        )

        total_duration = sum(dur for _, dur in domain_rows)

        domains = [{"domain": d, "duration_seconds": dur} for d, dur in domain_rows]
        browsers = [{"browser_name": b, "duration_seconds": dur} for b, dur in browser_rows]

        return {
            "time_entry_id": time_entry_id,
            "total_duration_seconds": total_duration,
            "domains": domains,
            "browsers": browsers
        }

    @staticmethod
    def list_usage_global(
        db: Session,
        user_id: Optional[int],
        time_entry_id: Optional[int],
        domain: Optional[str],
        browser_name: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        skip: int,
        limit: int,
        current_user: User
    ) -> Tuple[List[TimeEntryUrlUsage], int]:
        is_privileged = current_user.permissions.get("time_entries:view_all", False)
        if not is_privileged:
            user_id = current_user.id

        return URLUsageRepository.list_by_filters(
            db=db,
            organization_id=current_user.organization_id,
            user_id=user_id,
            time_entry_id=time_entry_id,
            domain=domain,
            browser_name=browser_name,
            start_time=start_date,
            end_time=end_date,
            skip=skip,
            limit=limit,
            sort_asc=False
        )
