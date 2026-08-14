from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from typing import Optional, List
from app.schemas.task_assignee import TaskAssigneeRead

class TaskBase(BaseModel):
    task_name: str
    description: Optional[str] = None
    status: str = "todo"
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    estimated_hours: Optional[float] = None
    time_tracked_seconds: int = 0
    completed_at: Optional[datetime] = None
    completed_by: Optional[int] = None

class TaskCreate(BaseModel):
    task_name: str
    description: Optional[str] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    estimated_hours: Optional[float] = None
    assignee_id: Optional[int] = None

class TaskUpdate(BaseModel):
    task_name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    estimated_hours: Optional[float] = None
    completed_at: Optional[datetime] = None
    completed_by: Optional[int] = None

class TaskRead(TaskBase):
    id: int
    organization_id: int
    project_id: int
    created_by: int
    created_at: datetime
    updated_at: datetime
    assignees: Optional[List[TaskAssigneeRead]] = None

    model_config = ConfigDict(from_attributes=True)
