from pydantic import BaseModel, ConfigDict
from datetime import datetime

from app.core.validation import Identifier


class TaskAssigneeCreate(BaseModel):
    user_id: Identifier

class TaskAssigneeRead(BaseModel):
    id: int
    task_id: int
    user_id: int
    assigned_by: int
    assigned_at: datetime

    model_config = ConfigDict(from_attributes=True)
