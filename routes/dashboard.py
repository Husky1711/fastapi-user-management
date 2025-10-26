"""
Dashboard APIs
Role-based dashboard endpoints for different user types
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, time
from typing import Dict, Any, List, Optional

from services.users import UserService
from services.auth import AuthService
from services.sessions import UserSessionService
from services.audit import AuditLogService
from services.auth import RefreshTokenService
from utils.database import get_db
from utils.rate_limit_dependency import RateLimitDependency
from models.user_model import User, RefreshToken, AuditLog
from utils.loggers import api_logger, auth_logger
from schemas.login import UserResponse
from schemas.dashboard import (
    UserDashboardOverview,
    UserActivityResponse,
    UserSessionsResponse,
    ProfileInfo,
    AdminDashboardOverview,
    AdminUsersStats,
    AdminActivityStats,
    ActivityItem,
    SessionInfo
)

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])
security = HTTPBearer()


# ============================================================================
# USER DASHBOARD (Phase 1)
# ============================================================================

@router.get("/user/overview", response_model=UserDashboardOverview)
async def get_user_dashboard_overview(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard"))
):
    """
    Get user's personal dashboard overview
    
    **Returns:**
    - User profile information
    - Active session count
    - Last login timestamp
    - Account creation date
    """
    try:
        # Verify JWT token and get user
        user = AuthService.get_current_user(db, credentials.credentials)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get active session count
        sessions = RefreshTokenService.get_user_tokens(db, user.id)
        active_sessions = [s for s in sessions if not s.is_revoked]
        
        # Get last login from audit logs
        last_login = user.last_login
        if not last_login:
            # Try to get from audit logs
            audit_logs = db.query(AuditLogService.get_logs_model()).filter(
                AuditLogService.get_logs_model().user_id == user.id,
                AuditLogService.get_logs_model().action == "login"
            ).order_by(
                AuditLogService.get_logs_model().created_at.desc()
            ).first()
            
            if audit_logs:
                last_login = audit_logs.created_at
        
        return {
            "profile": {
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "status": user.status,
                "organization_id": user.organization_id,
                "phone_number": user.phone_number,
                "is_2fa_enabled": getattr(user, 'is_2fa_enabled', False),
                "failed_login_attempts": getattr(user, 'failed_login_attempts', 0)
            },
            "active_sessions": len(active_sessions),
            "last_login": last_login.isoformat() if last_login else None,
            "account_created": user.created_at.isoformat() if user.created_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(
            f"User dashboard overview error: {str(e)}",
            user_id=user.id if 'user' in locals() else None,
            error=str(e),
            event_type="user_dashboard_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/user/activity", response_model=UserActivityResponse)
async def get_user_activity(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    limit: int = 20,
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard"))
):
    """
    Get user's account activity
    
    **Returns:**
    - Recent activity log
    - Login statistics (today, this week, this month)
    - Activity timeline
    """
    try:
        # Verify JWT token and get user
        user = AuthService.get_current_user(db, credentials.credentials)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get audit logs for this user
        from sqlalchemy import and_
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        today_start = datetime(now.year, now.month, now.day)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        # Recent activity (last 20 logs)
        recent_activity = db.query(AuditLog).filter(
            AuditLog.user_id == user.id
        ).order_by(
            AuditLog.created_at.desc()
        ).limit(limit).all()
        
        # Login statistics
        logins_today = db.query(AuditLog).filter(
            and_(
                AuditLog.user_id == user.id,
                AuditLog.action == "login",
                AuditLog.created_at >= today_start
            )
        ).count()
        
        logins_this_week = db.query(AuditLog).filter(
            and_(
                AuditLog.user_id == user.id,
                AuditLog.action == "login",
                AuditLog.created_at >= week_ago
            )
        ).count()
        
        logins_this_month = db.query(AuditLog).filter(
            and_(
                AuditLog.user_id == user.id,
                AuditLog.action == "login",
                AuditLog.created_at >= month_ago
            )
        ).count()
        
        # Format recent activity
        activity_list = []
        for log in recent_activity:
            activity_list.append({
                "action": log.event_type or log.action,
                "time": log.created_at.isoformat() if log.created_at else None,
                "ip_address": log.ip_address,
                "status": log.status,
                "resource_type": log.resource_type
            })
        
        return {
            "recent_activity": activity_list,
            "total_logins_today": logins_today,
            "total_logins_this_week": logins_this_week,
            "total_logins_this_month": logins_this_month
        }
        
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(
            f"User activity error: {str(e)}",
            user_id=user.id if 'user' in locals() else None,
            error=str(e),
            event_type="user_activity_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/user/sessions", response_model=UserSessionsResponse)
async def get_user_sessions_dashboard(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard"))
):
    """
    Get user's active sessions
    
    **Returns:**
    - All active sessions
    - Device information
    - Location info
    - Last activity time
    - IP address
    """
    try:
        # Verify JWT token and get user
        user = AuthService.get_current_user(db, credentials.credentials)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user's active sessions
        sessions = RefreshTokenService.get_user_tokens(db, user.id)
        active_sessions = [s for s in sessions if not s.is_revoked]
        
        # Format session data
        session_list = []
        for session in active_sessions:
            session_list.append({
                "id": session.id,
                "device": session.device_info or "Unknown Device",
                "location": session.ip_address,  # Could enhance with GeoIP lookup
                "last_active": session.created_at.isoformat() if session.created_at else None,
                "ip_address": session.ip_address,
                "expires_at": session.expires_at.isoformat() if session.expires_at else None
            })
        
        return {
            "active_sessions": session_list,
            "total_sessions": len(session_list),
            "can_revoke": True  # Users can revoke their own sessions
        }
        
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(
            f"User sessions dashboard error: {str(e)}",
            user_id=user.id if 'user' in locals() else None,
            error=str(e),
            event_type="user_sessions_dashboard_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# ============================================================================
# ADMIN DASHBOARD (Phase 2)
# ============================================================================

@router.get("/admin/overview", response_model=AdminDashboardOverview)
async def get_admin_dashboard_overview(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard"))
):
    """
    Get admin's dashboard overview with organization statistics
    
    **Returns:**
    - Total users in organization
    - Active users count
    - Active sessions count
    - Today's statistics (logins, new users, password resets)
    """
    try:
        # Verify JWT token and get user
        user = AuthService.get_current_user(db, credentials.credentials)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is admin
        if user.role not in ["admin", "super_admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        org_id = user.organization_id if hasattr(user, 'organization_id') else None
        
        # Get all users in organization
        all_users = db.query(User).filter(User.organization_id == org_id).all()
        total_users = len(all_users)
        active_users = len([u for u in all_users if u.status == "active"])
        
        # Get active sessions
        all_sessions = db.query(RefreshToken).join(User).filter(
            User.organization_id == org_id,
            RefreshToken.is_revoked == False
        ).all()
        active_sessions = len(all_sessions)
        
        # Get today's statistics
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, time.min)
        tomorrow_start = today_start + timedelta(days=1)
        
        # Today's logins
        from sqlalchemy import and_
        logins_today = db.query(AuditLog).join(
            User, AuditLog.user_id == User.id
        ).filter(
            User.organization_id == org_id,
            AuditLog.action == "login",
            AuditLog.status == "success",
            AuditLog.created_at >= today_start,
            AuditLog.created_at < tomorrow_start
        ).count()
        
        # Today's new users
        new_users_today = db.query(User).filter(
            User.organization_id == org_id,
            User.created_at >= today_start,
            User.created_at < tomorrow_start
        ).count()
        
        # Today's password resets
        password_resets_today = db.query(AuditLog).join(
            User, AuditLog.user_id == User.id
        ).filter(
            User.organization_id == org_id,
            AuditLog.action == "password_change",
            AuditLog.created_at >= today_start,
            AuditLog.created_at < tomorrow_start
        ).count()
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "active_sessions": active_sessions,
            "today_stats": {
                "logins": logins_today,
                "new_users": new_users_today,
                "password_resets": password_resets_today
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(
            f"Admin dashboard overview error: {str(e)}",
            user_id=user.id if 'user' in locals() else None,
            error=str(e),
            event_type="admin_dashboard_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/admin/users/stats", response_model=AdminUsersStats)
async def get_admin_users_stats(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard"))
):
    """
    Get user management statistics for admin
    
    **Returns:**
    - Total users count
    - Active/inactive/locked user counts
    - Users by status breakdown
    - Recent users list
    """
    try:
        # Verify JWT token and get user
        user = AuthService.get_current_user(db, credentials.credentials)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is admin
        if user.role not in ["admin", "super_admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        org_id = user.organization_id if hasattr(user, 'organization_id') else None
        
        # Get all users in organization
        all_users = db.query(User).filter(User.organization_id == org_id).all()
        
        total_users = len(all_users)
        active_users = len([u for u in all_users if u.status == "active"])
        locked_users = len([u for u in all_users if u.status == "locked"])
        inactive_users = total_users - active_users - locked_users
        
        # Recent users (last 10)
        recent_users = db.query(User).filter(
            User.organization_id == org_id
        ).order_by(User.created_at.desc()).limit(10).all()
        
        recent_users_list = []
        for u in recent_users:
            recent_users_list.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.role,
                "status": u.status,
                "created_at": u.created_at.isoformat() if u.created_at else None
            })
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "locked_users": locked_users,
            "users_by_status": {
                "active": active_users,
                "inactive": inactive_users,
                "locked": locked_users
            },
            "recent_users": recent_users_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(
            f"Admin users stats error: {str(e)}",
            user_id=user.id if 'user' in locals() else None,
            error=str(e),
            event_type="admin_users_stats_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/admin/activity/stats", response_model=AdminActivityStats)
async def get_admin_activity_stats(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    limit: int = 20,
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard"))
):
    """
    Get organization activity statistics for admin
    
    **Returns:**
    - Total activity today
    - Activity breakdown by type
    - Recent activity list
    """
    try:
        # Verify JWT token and get user
        user = AuthService.get_current_user(db, credentials.credentials)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is admin
        if user.role not in ["admin", "super_admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        org_id = user.organization_id if hasattr(user, 'organization_id') else None
        
        # Get today's activity
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, time.min)
        tomorrow_start = today_start + timedelta(days=1)
        
        # Total activity today
        total_activity_today = db.query(AuditLog).join(
            User, AuditLog.user_id == User.id
        ).filter(
            User.organization_id == org_id,
            AuditLog.created_at >= today_start,
            AuditLog.created_at < tomorrow_start
        ).count()
        
        # Activity by type
        from sqlalchemy import func
        activity_by_type = db.query(
            AuditLog.action,
            func.count(AuditLog.id)
        ).join(User, AuditLog.user_id == User.id).filter(
            User.organization_id == org_id,
            AuditLog.created_at >= today_start,
            AuditLog.created_at < tomorrow_start
        ).group_by(AuditLog.action).all()
        
        # Convert to dictionary
        activity_dict = {}
        for action, count in activity_by_type:
            activity_dict[action or "unknown"] = count
        
        # Recent activity
        recent_activity = db.query(AuditLog).join(
            User, AuditLog.user_id == User.id
        ).filter(
            User.organization_id == org_id
        ).order_by(AuditLog.created_at.desc()).limit(limit).all()
        
        recent_activity_list = []
        for log in recent_activity:
            recent_activity_list.append({
                "user_id": log.user_id,
                "username": db.query(User).filter(User.id == log.user_id).first().username if log.user_id else None,
                "action": log.event_type or log.action,
                "time": log.created_at.isoformat() if log.created_at else None,
                "status": log.status
            })
        
        return {
            "total_activity_today": total_activity_today,
            "activity_by_type": activity_dict,
            "recent_activity": recent_activity_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(
            f"Admin activity stats error: {str(e)}",
            user_id=user.id if 'user' in locals() else None,
            error=str(e),
            event_type="admin_activity_stats_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# ============================================================================
# ADD MORE DASHBOARD ENDPOINTS BELOW
# ============================================================================

