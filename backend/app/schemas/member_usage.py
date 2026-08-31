from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class MemberUsageOrganization(BaseModel):
    id: int
    name: Optional[str] = None


class MemberUsageMember(BaseModel):
    id: int
    name: str
    email: str
    role: str
    status: str
    designation: Optional[str] = None
    date_of_joining: Optional[date] = None
    date_of_birth: Optional[date] = None
    created_at: datetime
    updated_at: datetime
    organization: MemberUsageOrganization


class DailyActivityItem(BaseModel):
    date: date
    keyboard_strokes: int
    mouse_clicks: int
    mouse_movements: int
    activity_percentage: int


class ApplicationUsageItem(BaseModel):
    application_name: str
    duration_seconds: int
    duration: str
    usage_percentage: int


class DailyApplicationUsage(BaseModel):
    date: date
    applications: list[ApplicationUsageItem]


class UrlUsageItem(BaseModel):
    browser_name: str
    domain: str
    url: Optional[str] = None
    page_title: Optional[str] = None
    duration_seconds: int
    duration: str
    usage_percentage: int


class DailyUrlUsage(BaseModel):
    date: date
    urls: list[UrlUsageItem]


class MemberUsageResponse(BaseModel):
    member: MemberUsageMember
    start_date: date
    end_date: date
    daily_activity: list[DailyActivityItem]
    application_usage: list[DailyApplicationUsage]
    url_usage: list[DailyUrlUsage]
