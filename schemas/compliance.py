"""Request/response models for compliance write APIs."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CreateGroupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    organization_id: Optional[int] = None


class UpdateGroupRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None


class AddGroupMemberRequest(BaseModel):
    user_id: int
    expires_at: Optional[datetime] = None


class GrantGroupPermissionRequest(BaseModel):
    permission_name: str = Field(..., min_length=3, max_length=100)


class CreateApiKeyRequest(BaseModel):
    key_name: str = Field(..., min_length=1, max_length=100)
    user_id: Optional[int] = None
    permissions: Optional[List[str]] = None
    rate_limit_per_minute: int = Field(100, ge=1, le=10_000)
    rate_limit_per_hour: int = Field(1000, ge=1, le=100_000)
    expires_at: Optional[datetime] = None


class UpdateApiKeyRequest(BaseModel):
    key_name: Optional[str] = Field(None, min_length=1, max_length=100)
    permissions: Optional[List[str]] = None
    rate_limit_per_minute: Optional[int] = Field(None, ge=1, le=10_000)
    rate_limit_per_hour: Optional[int] = Field(None, ge=1, le=100_000)
    expires_at: Optional[datetime] = None
