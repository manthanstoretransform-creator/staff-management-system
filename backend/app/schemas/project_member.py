from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import date, datetime

class ProjectMemberCreate(BaseModel):
    user_id: int


class ProjectMembersAddRequest(BaseModel):
    """Members to attach to an existing project."""

    member_ids: list[int] = Field(..., min_length=1)

    @classmethod
    def _positive_ids(cls, value: list[int]):
        if any(member_id <= 0 for member_id in value):
            raise ValueError("member_ids must contain positive IDs")
        return value

    # Duplicate IDs are intentionally accepted: the service de-duplicates them
    # so a retry/batch payload is safe and its response can report the result.
    _validate_member_ids = field_validator("member_ids")(_positive_ids)


class ProjectMembersAddResponse(BaseModel):
    message: str
    project_id: int
    added_member_ids: list[int]
    already_assigned_member_ids: list[int]


class ProjectMemberUpdate(BaseModel):
    user_id: int = Field(..., gt=0)


class ProjectMemberRead(BaseModel):
    id: int
    organization_id: int
    project_id: int
    user_id: int
    joined_at: date
    created_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectMembersListResponse(BaseModel):
    items: list[ProjectMemberRead]
    page: int
    limit: int
    total: int
