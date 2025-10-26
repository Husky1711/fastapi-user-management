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
# ADMIN DASHBOARD SCHEMAS (Phase 2)
# ============================================================================

class TodayStats(BaseModel):
    """Today's statistics"""
    logins: int
    new_users: int
    password_resets: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "logins": 50,
                "new_users": 2,
                "password_resets": 5
            }
        }


class AdminDashboardOverview(BaseModel):
    """Admin dashboard overview response"""
    total_users: int
    active_users: int
    active_sessions: int
    today_stats: TodayStats
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_users": 150,
                "active_users": 120,
                "active_sessions": 85,
                "today_stats": {
                    "logins": 50,
                    "new_users": 2,
                    "password_resets": 5
                }
            }
        }


class UsersByStatus(BaseModel):
    """Users breakdown by status"""
    active: int
    inactive: int
    locked: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "active": 120,
                "inactive": 28,
                "locked": 2
            }
        }


class RecentUser(BaseModel):
    """Recent user information"""
    id: int
    username: str
    email: str
    role: str
    status: str
    created_at: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "username": "john_doe",
                "email": "john@example.com",
                "role": "user",
                "status": "active",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }


class AdminUsersStats(BaseModel):
    """Admin users statistics response"""
    total_users: int
    active_users: int
    locked_users: int
    users_by_status: UsersByStatus
    recent_users: List[RecentUser]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_users": 150,
                "active_users": 120,
                "locked_users": 2,
                "users_by_status": {
                    "active": 120,
                    "inactive": 28,
                    "locked": 2
                },
                "recent_users": [
                    {
                        "id": 1,
                        "username": "john_doe",
                        "email": "john@example.com",
                        "role": "user",
                        "status": "active",
                        "created_at": "2024-01-15T10:30:00Z"
                    }
                ]
            }
        }


class AdminActivityItem(BaseModel):
    """Activity item for admin dashboard"""
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: Optional[str] = None
    time: Optional[str] = None
    status: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 1,
                "username": "john_doe",
                "action": "login",
                "time": "2024-01-15T10:30:00Z",
                "status": "success"
            }
        }


class AdminActivityStats(BaseModel):
    """Admin activity statistics response"""
    total_activity_today: int
    activity_by_type: Dict[str, int]
    recent_activity: List[AdminActivityItem]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_activity_today": 500,
                "activity_by_type": {
                    "login": 200,
                    "logout": 150,
                    "password_change": 50,
                    "user_creation": 10
                },
                "recent_activity": [
                    {
                        "user_id": 1,
                        "username": "john_doe",
                        "action": "login",
                        "time": "2024-01-15T10:30:00Z",
                        "status": "success"
                    }
                ]
            }
        }


# ============================================================================
# ORGANIZATION ADMIN DASHBOARD SCHEMAS (Phase 3 - To be added)
# ============================================================================

# Placeholder for organization admin dashboard schemas


# ============================================================================
# SUPER ADMIN DASHBOARD SCHEMAS (Phase 4 - To be added)
# ============================================================================

# Placeholder for super admin dashboard schemas

