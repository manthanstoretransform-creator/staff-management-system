from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime

class URLUsageCreate(BaseModel):
    time_entry_id: int = Field(..., gt=0, description="Time entry ID associated with the URL usage")
    browser_name: str = Field(..., min_length=1, max_length=100, description="Browser name e.g. Google Chrome")
    domain: str = Field(..., min_length=1, max_length=255, description="Domain e.g. github.com")
    url: Optional[str] = Field(None, description="Full URL")
    page_title: Optional[str] = Field(None, description="Page title")
    duration_seconds: int = Field(..., ge=0, description="Duration spent in seconds")
    recorded_at: Optional[datetime] = Field(None, description="Time event was recorded by desktop")
    client_event_id: Optional[str] = Field(None, max_length=255, description="Client idempotency key")

class URLUsageBatchCreate(BaseModel):
    records: List[URLUsageCreate] = Field(..., min_length=1, description="List of URL usage records to sync")

class URLUsageRecord(BaseModel):
    id: int
    organization_id: int
    time_entry_id: int
    browser_name: str
    domain: str
    url: Optional[str] = None
    page_title: Optional[str] = None
    duration_seconds: int
    recorded_at: datetime
    created_at: datetime
    client_event_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class URLUsageResponse(BaseModel):
    success: bool = True
    message: str = "URL usage recorded successfully"
    data: URLUsageRecord

class URLUsageBatchSummaryData(BaseModel):
    accepted: int
    failed: int

class URLUsageBatchResponse(BaseModel):
    success: bool = True
    message: str = "URL usage batch synced successfully"
    data: URLUsageBatchSummaryData

class URLUsageListResponseData(BaseModel):
    items: List[URLUsageRecord]
    total: int
    skip: int
    limit: int

class URLUsageListResponse(BaseModel):
    success: bool = True
    data: URLUsageListResponseData

class URLUsageDomainSummary(BaseModel):
    domain: str
    duration_seconds: int

class URLUsageBrowserSummary(BaseModel):
    browser_name: str
    duration_seconds: int

class URLUsageSummaryData(BaseModel):
    time_entry_id: Optional[int] = None
    total_duration_seconds: int
    domains: List[URLUsageDomainSummary]
    browsers: List[URLUsageBrowserSummary]

class URLUsageSummaryResponse(BaseModel):
    success: bool = True
    data: URLUsageSummaryData
