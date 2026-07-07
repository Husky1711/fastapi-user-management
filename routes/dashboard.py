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
from services.users.role_scope import filter_users_for_viewer
from services.auth import AuthService
from services.sessions import UserSessionService
from services.audit import AuditLogService
from services.auth import RefreshTokenService
from utils.database import get_db
from utils.rate_limit_dependency import RateLimitDependency
from models.user_model import User, RefreshToken, AuditLog, Organization
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
        
        org = (
            db.query(Organization).filter(Organization.id == user.organization_id).first()
            if user.organization_id
            else None
        )

        return {
            "profile": {
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "status": user.status,
                "organization_id": user.organization_id,
                "organization_name": org.name if org else None,
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
        if user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        org_id = user.organization_id if hasattr(user, 'organization_id') else None
        
        # Users this admin can manage (regular users in their organization)
        all_users = filter_users_for_viewer(db.query(User), "admin", org_id).all()
        total_users = len(all_users)
        active_users = len([u for u in all_users if u.status == "active"])
        viewable_user_ids = [u.id for u in all_users]
        
        # Active sessions for manageable users only
        session_query = db.query(RefreshToken).filter(RefreshToken.is_revoked == False)
        if viewable_user_ids:
            session_query = session_query.filter(RefreshToken.user_id.in_(viewable_user_ids))
        else:
            session_query = session_query.filter(False)
        active_sessions = session_query.count()
        
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
        new_users_today = (
            filter_users_for_viewer(db.query(User), "admin", org_id)
            .filter(
                User.created_at >= today_start,
                User.created_at < tomorrow_start,
            )
            .count()
        )
        
        # Today's password resets
        password_reset_query = db.query(AuditLog).join(
            User, AuditLog.user_id == User.id
        ).filter(
            AuditLog.action == "password_change",
            AuditLog.created_at >= today_start,
            AuditLog.created_at < tomorrow_start,
        )
        if viewable_user_ids:
            password_reset_query = password_reset_query.filter(
                User.id.in_(viewable_user_ids)
            )
        else:
            password_reset_query = password_reset_query.filter(False)
        password_resets_today = password_reset_query.count()
        
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
        if user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        org_id = user.organization_id if hasattr(user, 'organization_id') else None
        
        # Users this admin can manage (regular users in their organization)
        all_users = filter_users_for_viewer(db.query(User), "admin", org_id).all()
        
        total_users = len(all_users)
        active_users = len([u for u in all_users if u.status == "active"])
        locked_users = len([u for u in all_users if u.status == "locked"])
        inactive_users = total_users - active_users - locked_users
        
        # Recent users (last 10)
        recent_users = (
            filter_users_for_viewer(db.query(User), "admin", org_id)
            .order_by(User.created_at.desc())
            .limit(10)
            .all()
        )
        
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
        if user.role != "admin":
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
# ORGANIZATION ADMIN DASHBOARD (Phase 3)
# ============================================================================

@router.get("/organization-admin/overview")
async def get_organization_admin_overview(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard"))
):
    """
    Get organization admin's dashboard overview
    
    **Returns:**
    - Organization information
    - Total users and roles breakdown
    - Active sessions count
    - Today's statistics
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
        
        # Check if user is organization admin
        if user.role != "organization_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization admin access required"
            )
        
        org_id = user.organization_id if hasattr(user, 'organization_id') else None
        
        # Users this org admin can manage (excludes system-wide super admins)
        all_users = filter_users_for_viewer(
            db.query(User), "organization_admin", org_id
        ).all()
        total_users = len(all_users)
        
        # Count users by role
        admins_count = len([u for u in all_users if u.role == "admin"])
        org_admins_count = len([u for u in all_users if u.role == "organization_admin"])
        regular_users_count = len([u for u in all_users if u.role == "user"])
        
        # Active users
        active_users = len([u for u in all_users if u.status == "active"])
        viewable_user_ids = [u.id for u in all_users]
        
        # Active sessions for manageable users only
        session_query = db.query(RefreshToken).filter(RefreshToken.is_revoked == False)
        if viewable_user_ids:
            session_query = session_query.filter(RefreshToken.user_id.in_(viewable_user_ids))
        else:
            session_query = session_query.filter(False)
        active_sessions = session_query.count()
        
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
        new_users_today = (
            filter_users_for_viewer(db.query(User), "organization_admin", org_id)
            .filter(
                User.created_at >= today_start,
                User.created_at < tomorrow_start,
            )
            .count()
        )
        
        return {
            "organization_id": org_id,
            "total_users": total_users,
            "active_users": active_users,
            "users_by_role": {
                "admins": admins_count,
                "organization_admins": org_admins_count,
                "users": regular_users_count
            },
            "active_sessions": active_sessions,
            "today_stats": {
                "logins": logins_today,
                "new_users": new_users_today
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(
            f"Organization admin dashboard overview error: {str(e)}",
            user_id=user.id if 'user' in locals() else None,
            error=str(e),
            event_type="org_admin_dashboard_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/organization-admin/users/stats")
async def get_organization_admin_users_stats(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard"))
):
    """
    Get organization user management statistics
    
    **Returns:**
    - User counts by status and role
    - Recent users
    - Role distribution
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
        
        # Check if user is organization admin
        if user.role != "organization_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization admin access required"
            )
        
        org_id = user.organization_id if hasattr(user, 'organization_id') else None
        
        all_users = filter_users_for_viewer(
            db.query(User), "organization_admin", org_id
        ).all()
        
        # Count by role
        admin_count = len([u for u in all_users if u.role == "admin"])
        org_admin_count = len([u for u in all_users if u.role == "organization_admin"])
        user_count = len([u for u in all_users if u.role == "user"])
        
        # Count by status
        active_count = len([u for u in all_users if u.status == "active"])
        inactive_count = len([u for u in all_users if u.status == "inactive"])
        locked_count = len([u for u in all_users if u.status == "locked"])
        
        # Recent users (last 10)
        recent_users = (
            filter_users_for_viewer(db.query(User), "organization_admin", org_id)
            .order_by(User.created_at.desc())
            .limit(10)
            .all()
        )
        
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
            "total_users": len(all_users),
            "users_by_role": {
                "admins": admin_count,
                "organization_admins": org_admin_count,
                "users": user_count
            },
            "users_by_status": {
                "active": active_count,
                "inactive": inactive_count,
                "locked": locked_count
            },
            "recent_users": recent_users_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(
            f"Organization admin users stats error: {str(e)}",
            user_id=user.id if 'user' in locals() else None,
            error=str(e),
            event_type="org_admin_users_stats_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/organization-admin/sessions/stats")
async def get_organization_admin_sessions_stats(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard"))
):
    """
    Get organization session statistics
    
    **Returns:**
    - Total and active sessions
    - Sessions by device type
    - Recent sessions
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
        
        # Check if user is organization admin
        if user.role != "organization_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization admin access required"
            )
        
        org_id = user.organization_id if hasattr(user, 'organization_id') else None
        viewable_user_ids = [
            u.id
            for u in filter_users_for_viewer(
                db.query(User), "organization_admin", org_id
            ).all()
        ]
        
        session_query = db.query(RefreshToken)
        if viewable_user_ids:
            session_query = session_query.filter(RefreshToken.user_id.in_(viewable_user_ids))
        else:
            session_query = session_query.filter(False)
        all_sessions = session_query.all()
        
        total_sessions = len(all_sessions)
        active_sessions = len([s for s in all_sessions if not s.is_revoked])
        
        # Recent sessions (last 20)
        recent_query = db.query(RefreshToken)
        if viewable_user_ids:
            recent_query = recent_query.filter(RefreshToken.user_id.in_(viewable_user_ids))
        else:
            recent_query = recent_query.filter(False)
        recent_sessions = recent_query.order_by(RefreshToken.created_at.desc()).limit(20).all()
        
        recent_sessions_list = []
        for s in recent_sessions:
            recent_sessions_list.append({
                "id": s.id,
                "user_id": s.user_id,
                "device_info": s.device_info or "Unknown",
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "is_revoked": s.is_revoked
            })
        
        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "revoked_sessions": total_sessions - active_sessions,
            "recent_sessions": recent_sessions_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(
            f"Organization admin sessions stats error: {str(e)}",
            user_id=user.id if 'user' in locals() else None,
            error=str(e),
            event_type="org_admin_sessions_stats_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# ============================================================================
# SUPER ADMIN DASHBOARD (Phase 4)
# ============================================================================

@router.get("/super-admin/overview")
async def get_super_admin_overview(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard"))
):
    """
    Get super admin's system-wide overview
    
    **Returns:**
    - Total organizations, users, admins, sessions
    - Active sessions count
    - System health status
    - Today's statistics
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
        
        # Check if user is super admin
        if user.role != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Super admin access required"
            )
        
        # Check cache first (5 minute TTL for super admin queries)
        from services.core import cache_service
        cache_key = "super_admin:overview"
        cached_result = cache_service.get_cache(cache_key)
        if cached_result:
            return cached_result
        
        # Get all users in system
        all_users = db.query(User).all()
        total_users = len(all_users)
        
        # Count users by role
        super_admin_count = len([u for u in all_users if u.role == "super_admin"])
        org_admin_count = len([u for u in all_users if u.role == "organization_admin"])
        admin_count = len([u for u in all_users if u.role == "admin"])
        user_count = len([u for u in all_users if u.role == "user"])
        
        # Active users
        active_users = len([u for u in all_users if u.status == "active"])
        
        # Get all active sessions
        all_sessions = db.query(RefreshToken).filter(
            RefreshToken.is_revoked == False
        ).all()
        active_sessions = len(all_sessions)
        total_sessions = db.query(RefreshToken).count()
        
        # Count organizations (get unique org IDs)
        org_ids = db.query(User.organization_id).distinct().all()
        total_organizations = len([org[0] for org in org_ids if org[0] is not None])
        
        # Get today's statistics
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, time.min)
        tomorrow_start = today_start + timedelta(days=1)
        
        # Today's audit logs
        total_audit_logs_today = db.query(AuditLog).filter(
            AuditLog.created_at >= today_start,
            AuditLog.created_at < tomorrow_start
        ).count()
        
        # Today's logins
        logins_today = db.query(AuditLog).filter(
            AuditLog.action == "login",
            AuditLog.status == "success",
            AuditLog.created_at >= today_start,
            AuditLog.created_at < tomorrow_start
        ).count()
        
        # Today's new users
        new_users_today = db.query(User).filter(
            User.created_at >= today_start,
            User.created_at < tomorrow_start
        ).count()
        
        result = {
            "total_organizations": total_organizations,
            "total_users": total_users,
            "active_users": active_users,
            "total_admins": org_admin_count + admin_count,
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "users_by_role": {
                "super_admin": super_admin_count,
                "organization_admin": org_admin_count,
                "admin": admin_count,
                "user": user_count
            },
            "today_stats": {
                "logins": logins_today,
                "new_users": new_users_today,
                "total_audit_logs": total_audit_logs_today
            }
        }
        
        # Cache the result for 1 minute (60 seconds) to reduce cache stampedes
        cache_service.set_cache(cache_key, result, ttl=60)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(
            f"Super admin dashboard overview error: {str(e)}",
            user_id=user.id if 'user' in locals() else None,
            error=str(e),
            event_type="super_admin_dashboard_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/super-admin/users/stats")
async def get_super_admin_users_stats(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard"))
):
    """
    Get system-wide user statistics
    
    **Returns:**
    - Total users by role and status
    - Users created today/this week/this month
    - Recent users
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
        
        # Check if user is super admin
        if user.role != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Super admin access required"
            )
        
        # Get all users
        all_users = db.query(User).all()
        
        # Count by role
        super_admin_count = len([u for u in all_users if u.role == "super_admin"])
        org_admin_count = len([u for u in all_users if u.role == "organization_admin"])
        admin_count = len([u for u in all_users if u.role == "admin"])
        user_count = len([u for u in all_users if u.role == "user"])
        
        # Count by status
        active_count = len([u for u in all_users if u.status == "active"])
        inactive_count = len([u for u in all_users if u.status == "inactive"])
        locked_count = len([u for u in all_users if u.status == "locked"])
        
        # Get time ranges
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        today_start = datetime.combine(today, time.min)
        week_start = datetime.combine(week_ago, time.min)
        month_start = datetime.combine(month_ago, time.min)
        tomorrow_start = today_start + timedelta(days=1)
        
        # Users created in time ranges
        users_today = db.query(User).filter(
            User.created_at >= today_start,
            User.created_at < tomorrow_start
        ).count()
        
        users_this_week = db.query(User).filter(
            User.created_at >= week_start
        ).count()
        
        users_this_month = db.query(User).filter(
            User.created_at >= month_start
        ).count()
        
        # Recent users (last 20)
        recent_users = db.query(User).order_by(User.created_at.desc()).limit(20).all()
        
        recent_users_list = []
        for u in recent_users:
            recent_users_list.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.role,
                "status": u.status,
                "organization_id": u.organization_id,
                "created_at": u.created_at.isoformat() if u.created_at else None
            })
        
        return {
            "total_users": len(all_users),
            "active_users": active_count,
            "locked_users": locked_count,
            "users_by_role": {
                "super_admin": super_admin_count,
                "organization_admin": org_admin_count,
                "admin": admin_count,
                "user": user_count
            },
            "users_by_status": {
                "active": active_count,
                "inactive": inactive_count,
                "locked": locked_count
            },
            "users_today": users_today,
            "users_this_week": users_this_week,
            "users_this_month": users_this_month,
            "recent_users": recent_users_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(
            f"Super admin users stats error: {str(e)}",
            user_id=user.id if 'user' in locals() else None,
            error=str(e),
            event_type="super_admin_users_stats_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/super-admin/organizations/stats")
async def get_super_admin_organizations_stats(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard"))
):
    """
    Get organization statistics across the system
    
    **Returns:**
    - Total organizations count
    - Organizations by size
    - Active vs inactive orgs
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
        
        # Check if user is super admin
        if user.role != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Super admin access required"
            )
        
        # Get all distinct organization IDs
        org_ids = db.query(User.organization_id).distinct().all()
        all_org_ids = [org[0] for org in org_ids if org[0] is not None]
        total_organizations = len(all_org_ids)
        
        # Count organizations by size
        small_orgs = 0  # < 10 users
        medium_orgs = 0  # 10-100 users
        large_orgs = 0  # > 100 users
        
        for org_id in all_org_ids:
            user_count = db.query(User).filter(User.organization_id == org_id).count()
            if user_count < 10:
                small_orgs += 1
            elif user_count <= 100:
                medium_orgs += 1
            else:
                large_orgs += 1
        
        # Count organizations with at least one active user
        active_orgs = 0
        organizations_list = []
        for org_id in all_org_ids:
            org = db.query(Organization).filter(Organization.id == org_id).first()
            user_count = db.query(User).filter(User.organization_id == org_id).count()
            active_users = db.query(User).filter(
                User.organization_id == org_id,
                User.status == "active"
            ).count()
            if active_users > 0:
                active_orgs += 1
            organizations_list.append({
                "id": org_id,
                "name": org.name if org else f"Organization {org_id}",
                "status": org.status if org else "unknown",
                "total_users": user_count,
                "active_users": active_users,
            })

        organizations_list.sort(key=lambda item: item["id"])
        
        return {
            "total_organizations": total_organizations,
            "active_organizations": active_orgs,
            "inactive_organizations": total_organizations - active_orgs,
            "organizations_by_size": {
                "small": small_orgs,
                "medium": medium_orgs,
                "large": large_orgs
            },
            "organizations": organizations_list,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(
            f"Super admin organizations stats error: {str(e)}",
            user_id=user.id if 'user' in locals() else None,
            error=str(e),
            event_type="super_admin_orgs_stats_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/super-admin/sessions/stats")
async def get_super_admin_sessions_stats(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard"))
):
    """
    Get system-wide session statistics
    
    **Returns:**
    - Total and active sessions
    - Sessions by status
    - Recent sessions
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
        
        # Check if user is super admin
        if user.role != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Super admin access required"
            )
        
        # Get all sessions
        all_sessions = db.query(RefreshToken).all()
        total_sessions = len(all_sessions)
        active_sessions = len([s for s in all_sessions if not s.is_revoked])
        revoked_sessions = total_sessions - active_sessions
        
        # Recent sessions (last 30)
        recent_sessions = db.query(RefreshToken).order_by(
            RefreshToken.created_at.desc()
        ).limit(30).all()
        
        recent_sessions_list = []
        for s in recent_sessions:
            recent_sessions_list.append({
                "id": s.id,
                "user_id": s.user_id,
                "device_info": s.device_info or "Unknown",
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "is_revoked": s.is_revoked
            })
        
        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "revoked_sessions": revoked_sessions,
            "recent_sessions": recent_sessions_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(
            f"Super admin sessions stats error: {str(e)}",
            user_id=user.id if 'user' in locals() else None,
            error=str(e),
            event_type="super_admin_sessions_stats_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# ============================================================================
# ADD MORE DASHBOARD ENDPOINTS BELOW
# ============================================================================

