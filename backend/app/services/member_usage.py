from collections import defaultdict
from datetime import date
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.member import MemberRepository
from app.repositories.member_usage import MemberUsageRepository
from app.services.member_service import MemberService
from app.services.time_tracking import TimeTrackingService

_utc_start = TimeTrackingService._utc_start
_utc_end = TimeTrackingService._utc_end
_hours = TimeTrackingService._hours

# Unpaginated per-day breakdowns (app usage, URL usage) mean an unbounded range could
# return years of nested data in one response -- see docs/Member_Usage_API.md.
MAX_RANGE_DAYS = 31


class MemberUsageService:
    @staticmethod
    def _resolve_range(
        single_date: Optional[date], start_date: Optional[date], end_date: Optional[date]
    ) -> tuple[date, date]:
        if single_date and (start_date or end_date):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Provide either 'date' or 'start_date'/'end_date', not both.")
        if bool(start_date) != bool(end_date):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "start_date and end_date must be provided together.")
        if not single_date and not (start_date and end_date):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Provide 'date' or both 'start_date' and 'end_date'.")

        if single_date:
            effective_start, effective_end = single_date, single_date
        else:
            effective_start, effective_end = start_date, end_date
            if effective_start > effective_end:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "start_date cannot be after end_date.")

        if (effective_end - effective_start).days + 1 > MAX_RANGE_DAYS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Date range cannot exceed {MAX_RANGE_DAYS} days.")
        return effective_start, effective_end

    @staticmethod
    def _member_payload(member: User, organization_name: Optional[str]) -> dict:
        return {
            "id": member.id,
            "name": member.name,
            "email": member.email,
            "role": member.role_name,
            "status": member.status,
            "designation": member.designation,
            "date_of_joining": member.date_of_joining,
            "date_of_birth": member.date_of_birth,
            "created_at": member.created_at,
            "updated_at": member.updated_at,
            "organization": {"id": member.organization_id, "name": organization_name},
        }

    @staticmethod
    def _daily_activity(rows) -> list[dict]:
        return [
            {
                "date": row.day,
                "keyboard_strokes": int(row.keyboard_strokes or 0),
                "mouse_clicks": int(row.mouse_clicks or 0),
                "mouse_movements": int(row.mouse_movements or 0),
                "activity_percentage": round(float(row.activity_percentage)) if row.activity_percentage is not None else 0,
            }
            for row in rows
        ]

    @staticmethod
    def _daily_app_usage(rows) -> list[dict]:
        by_day = defaultdict(list)
        for row in rows:
            by_day[row.day].append(row)
        result = []
        for day in sorted(by_day):
            day_rows = by_day[day]
            total = sum(int(row.duration_seconds or 0) for row in day_rows)
            applications = []
            for row in day_rows:
                seconds = int(row.duration_seconds or 0)
                applications.append({
                    "application_name": row.application_name,
                    "duration_seconds": seconds,
                    "duration": _hours(seconds),
                    "usage_percentage": round(seconds / total * 100) if total else 0,
                })
            result.append({"date": day, "applications": applications})
        return result

    @staticmethod
    def _daily_url_usage(rows) -> list[dict]:
        by_day = defaultdict(list)
        for row in rows:
            by_day[row.day].append(row)
        result = []
        for day in sorted(by_day):
            day_rows = by_day[day]
            total = sum(int(row.duration_seconds or 0) for row in day_rows)
            urls = []
            for row in day_rows:
                seconds = int(row.duration_seconds or 0)
                urls.append({
                    "browser_name": row.browser_name,
                    "domain": row.domain,
                    "url": row.url,
                    "page_title": row.page_title,
                    "duration_seconds": seconds,
                    "duration": _hours(seconds),
                    "usage_percentage": round(seconds / total * 100) if total else 0,
                })
            result.append({"date": day, "urls": urls})
        return result

    @staticmethod
    def build_details(
        db: Session,
        current_user: User,
        member_id: int,
        single_date: Optional[date],
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> dict:
        effective_start, effective_end = MemberUsageService._resolve_range(single_date, start_date, end_date)

        member = MemberService.get(db, current_user, member_id)
        organization_id = member.organization_id

        start_time = _utc_start(effective_start)
        end_time = _utc_end(effective_end)

        activity_rows = MemberUsageRepository.daily_activity(db, organization_id, member_id, start_time, end_time)
        app_rows = MemberUsageRepository.daily_app_usage(db, organization_id, member_id, start_time, end_time)
        url_rows = MemberUsageRepository.daily_url_usage(db, organization_id, member_id, start_time, end_time)

        organization_name = MemberRepository.organization_name(db, organization_id)
        member_payload = MemberUsageService._member_payload(member, organization_name)

        return {
            "member": member_payload,
            "start_date": effective_start,
            "end_date": effective_end,
            "daily_activity": MemberUsageService._daily_activity(activity_rows),
            "application_usage": MemberUsageService._daily_app_usage(app_rows),
            "url_usage": MemberUsageService._daily_url_usage(url_rows),
        }
