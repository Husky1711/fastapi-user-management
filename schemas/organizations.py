from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class OrganizationStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class OrganizationCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    status: OrganizationStatus = OrganizationStatus.ACTIVE

    class Config:
        use_enum_values = True


class OrganizationUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    slug: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    status: Optional[OrganizationStatus] = None

    class Config:
        use_enum_values = True


class OrganizationResponse(BaseModel):
    id: int
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    status: str
    total_users: int = 0
    active_users: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrganizationListResponse(BaseModel):
    organizations: List[OrganizationResponse]


class OrganizationMutationResponse(BaseModel):
    success: bool
    message: str
    organization: Optional[OrganizationResponse] = None


class OrganizationSettingUpsertRequest(BaseModel):
    value: Any = Field(..., description="JSON-serializable setting value")


class OrganizationSettingsResponse(BaseModel):
    success: bool = True
    organization_id: int
    settings: dict
    known_keys: List[str] = []


class OrganizationSettingMutationResponse(BaseModel):
    success: bool
    organization_id: int
    setting_key: str
    setting_value: Optional[Any] = None
    message: Optional[str] = None
