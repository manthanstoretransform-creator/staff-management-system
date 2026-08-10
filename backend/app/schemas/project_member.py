from pydantic import BaseModel, ConfigDict
from datetime import date, datetime

class ProjectMemberCreate(BaseModel):
    user_id: int

class ProjectMemberRead(BaseModel):
    id: int
    organization_id: int
    project_id: int
    user_id: int
    joined_at: date
    created_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
