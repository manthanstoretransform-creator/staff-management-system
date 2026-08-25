from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List

class AppUsageCreate(BaseModel):
    application_name: str = Field(..., max_length=255, min_length=1)
    window_title: Optional[str] = None
    duration_seconds: int = Field(..., ge=1)
    recorded_at: Optional[datetime] = None

class AppUsageBatchCreate(BaseModel):
    records: List[AppUsageCreate]

class AppUsageResponse(BaseModel):
    id: int
    organization_id: int
    time_entry_id: int
    application_name: str
    window_title: Optional[str] = None
    duration_seconds: int
    recorded_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AppUsageListResponse(BaseModel):
    items: List[AppUsageResponse]
    total: int

class AppUsageSummaryItem(BaseModel):
    application_name: str
    duration_seconds: int
    percentage: float

class AppUsageSummaryResponse(BaseModel):
    time_entry_id: Optional[int] = None
    total_duration_seconds: int
    applications: List[AppUsageSummaryItem]
