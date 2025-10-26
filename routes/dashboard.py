"""
Dashboard APIs
Role-based dashboard endpoints for different user types
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
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

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])
security = HTTPBearer()


# ============================================================================
# USER DASHBOARD (Phase 1)
# ============================================================================

@router.get("/user/overview")
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
                "organization_id": user.organization_id
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


@router.get("/user/activity")
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


@router.get("/user/sessions")
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
# ADD MORE DASHBOARD ENDPOINTS BELOW
# ============================================================================

