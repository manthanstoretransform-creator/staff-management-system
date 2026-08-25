from pydantic import BaseModel, Field, validator
from datetime import date, datetime
from typing import Optional, List
from enum import Enum

class ProjectStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    PENDING = "pending"
    TODO = "todo"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"

class BillingType(str, Enum):
    FREE = "free"
    HOURLY = "hourly"
    FIXED = "fixed"

class ProjectCreateRequest(BaseModel):
    """Schema for creating a new project"""
    project_name: str = Field(..., min_length=1, max_length=150, description="Name of the project")
    description: Optional[str] = Field(None, max_length=1000, description="Project description")
    organization_id: int = Field(..., gt=0, description="Organization ID")
    start_date: Optional[date] = Field(None, description="Project start date")
    deadline: Optional[date] = Field(None, description="Project deadline")
    is_billable: bool = Field(True, description="Whether project is billable")
    billing_type: BillingType = Field(BillingType.FREE, description="Billing type")
    fixed_hours: Optional[float] = Field(None, gt=0, description="Fixed hours for project")
    leader_id: Optional[int] = Field(None, gt=0, description="Project leader ID")
    status_id: Optional[int] = Field(None, gt=0, description="Project status ID")

class ProjectUpdateRequest(BaseModel):
    """Schema for updating an existing project"""
    project_name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=1000)
    start_date: Optional[date] = None
    deadline: Optional[date] = None
    completed_at: Optional[datetime] = None
    is_billable: Optional[bool] = None
    status: Optional[ProjectStatus] = None
    billing_type: Optional[BillingType] = None
    fixed_hours: Optional[float] = Field(None, gt=0)
    leader_id: Optional[int] = Field(None, gt=0)
    status_id: Optional[int] = Field(None, gt=0)

class ProjectPatchRequest(BaseModel):
    """Schema for partial update of a project (PATCH)"""
    project_name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=1000)
    start_date: Optional[date] = None
    deadline: Optional[date] = None
    completed_at: Optional[datetime] = None
    is_billable: Optional[bool] = None
    status: Optional[ProjectStatus] = None
    billing_type: Optional[BillingType] = None
    fixed_hours: Optional[float] = Field(None, gt=0)
    leader_id: Optional[int] = Field(None, gt=0)
    status_id: Optional[int] = Field(None, gt=0)

class ProjectResponse(BaseModel):
    """Schema for project response"""
    id: int
    organization_id: int
    project_name: str
    description: Optional[str]
    status: str
    status_id: Optional[int]
    leader_id: Optional[int]
    deadline: Optional[date]
    billing_type: str
    fixed_hours: Optional[float]
    start_date: Optional[date]
    completed_at: Optional[datetime]
    is_billable: bool
    time_tracked_seconds: int
    created_by: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PaginationMetadata(BaseModel):
    """Pagination metadata"""
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")

class ProjectListResponse(BaseModel):
    """Schema for paginated project list response"""
    data: List[ProjectResponse] = Field(..., description="List of projects")
    pagination: PaginationMetadata = Field(..., description="Pagination metadata")

class ErrorResponse(BaseModel):
    """Schema for error response"""
    status_code: int = Field(..., description="HTTP status code")
    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")
