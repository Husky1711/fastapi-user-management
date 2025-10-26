"""
Dashboard API Schemas
Pydantic models for dashboard responses
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any


# ============================================================================
# USER DASHBOARD SCHEMAS
# ============================================================================

class ProfileInfo(BaseModel):
    """User profile information"""
    username: str
    email: str
    role: str
    status: str
    organization_id: Optional[int] = None
    phone_number: Optional[str] = None
    is_2fa_enabled: Optional[bool] = Field(None, description="Whether 2FA is enabled")
    failed_login_attempts: Optional[int] = Field(None, description="Number of failed login attempts")
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "john_doe",
                "email": "john@example.com",
                "role": "user",
                "status": "active",
                "organization_id": 1,
                "phone_number": "1234567890",
                "is_2fa_enabled": False,
                "failed_login_attempts": 0
            }
        }


class UserDashboardOverview(BaseModel):
    """User dashboard overview response"""
    profile: ProfileInfo
    active_sessions: int = Field(description="Number of active sessions")
    last_login: Optional[str] = Field(None, description="Last login timestamp (ISO format)")
    account_created: Optional[str] = Field(None, description="Account creation timestamp (ISO format)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "profile": {
                    "username": "john_doe",
                    "email": "john@example.com",
                    "role": "user",
                    "status": "active",
                    "organization_id": 1
                },
                "active_sessions": 3,
                "last_login": "2024-01-15T10:30:00",
                "account_created": "2024-01-01T00:00:00"
            }
        }


class ActivityItem(BaseModel):
    """Single activity log item"""
    action: str
    time: Optional[str] = None
    ip_address: Optional[str] = None
    status: Optional[str] = None
    resource_type: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "action": "login",
                "time": "2024-01-15T10:30:00",
                "ip_address": "192.168.1.1",
                "status": "success",
                "resource_type": "user"
            }
        }


class UserActivityResponse(BaseModel):
    """User activity response"""
    recent_activity: List[ActivityItem]
    total_logins_today: int = Field(description="Total logins today")
    total_logins_this_week: int = Field(description="Total logins this week")
    total_logins_this_month: int = Field(description="Total logins this month")
    
    class Config:
        json_schema_extra = {
            "example": {
                "recent_activity": [
                    {
                        "action": "login",
                        "time": "2024-01-15T10:30:00",
                        "ip_address": "192.168.1.1",
                        "status": "success",
                        "resource_type": "user"
                    }
                ],
                "total_logins_today": 1,
                "total_logins_this_week": 5,
                "total_logins_this_month": 20
            }
        }


class SessionInfo(BaseModel):
    """Session information"""
    id: int
    device: str
    location: str
    last_active: Optional[str] = None
    ip_address: Optional[str] = None
    expires_at: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 123,
                "device": "Chrome on Windows",
                "location": "New York, USA",
                "last_active": "2024-01-15T10:30:00",
                "ip_address": "192.168.1.1",
                "expires_at": "2024-01-16T10:30:00"
            }
        }


class UserSessionsResponse(BaseModel):
    """User sessions response"""
    active_sessions: List[SessionInfo]
    total_sessions: int = Field(description="Total number of active sessions")
    can_revoke: bool = Field(description="Whether user can revoke sessions")
    
    class Config:
        json_schema_extra = {
            "example": {
                "active_sessions": [
                    {
                        "id": 123,
                        "device": "Chrome on Windows",
                        "location": "New York, USA",
                        "last_active": "2024-01-15T10:30:00",
                        "ip_address": "192.168.1.1",
                        "expires_at": "2024-01-16T10:30:00"
                    }
                ],
                "total_sessions": 3,
                "can_revoke": True
            }
        }


# ============================================================================
# ADMIN DASHBOARD SCHEMAS (Phase 2 - To be added)
# ============================================================================

# Placeholder for admin dashboard schemas


# ============================================================================
# ORGANIZATION ADMIN DASHBOARD SCHEMAS (Phase 3 - To be added)
# ============================================================================

# Placeholder for organization admin dashboard schemas


# ============================================================================
# SUPER ADMIN DASHBOARD SCHEMAS (Phase 4 - To be added)
# ============================================================================

# Placeholder for super admin dashboard schemas

