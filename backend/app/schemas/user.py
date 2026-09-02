from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any
from datetime import datetime

class UserBase(BaseModel):
    username: str
    email: str
    name: str
    designation: Optional[str] = None
    role_name: str
    permissions: Dict[str, Any] = Field(default_factory=dict)
    wp_capabilities: Optional[Dict[str, Any]] = None
    idle_enabled: bool = True
    idle_minutes: int = 5
    capture_frequency: int
    status: str = "active"
    is_active: bool = True

class UserCreate(UserBase):
    organization_id: int
    hubstaff_user_id: Optional[str] = None

class UserRead(UserBase):
    id: int
    organization_id: int
    hubstaff_user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UserUpdate(BaseModel):
    name: Optional[str] = None
    designation: Optional[str] = None
    role_name: Optional[str] = None
    status: Optional[str] = None
    permissions: Optional[Dict[str, Any]] = None
    wp_capabilities: Optional[Dict[str, Any]] = None
    idle_enabled: Optional[bool] = None
    #: Minutes of inactivity before the idle popup. Must be positive: a zero
    #: or negative threshold would make every poll look like an idle period.
    idle_minutes: Optional[int] = Field(None, gt=0)
    capture_frequency: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class LoginRequest(BaseModel):
    username: str
    password: str

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "username": "provider-user@example.com",
                    "password": "provider-password",
                }
            ]
        }
    )

class PermissionSchema(BaseModel):
    name: str
    permissions: Dict[str, Any] = Field(default_factory=dict)


class HubstaffLoginPayload(BaseModel):
    user_id: int
    username: str
    email: str
    name: str
    hubstaff_user_id: str
    hubstaff_designation: Optional[str] = None
    organization_id: int         
    idle_enabled: bool = True
    idle_minutes: int = Field(5, gt=0)
    capture_frequency: int
    permission_schema: PermissionSchema

class DevLoginRequest(BaseModel):
    email: str
    password: str

class EmployeeListItem(BaseModel):
    id: int
    name: str
    email: str
    role_name: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class EmployeeDetail(EmployeeListItem):
    organization_id: int

    model_config = ConfigDict(from_attributes=True)

class EmployeeStatusUpdate(BaseModel):
    is_active: bool
