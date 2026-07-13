"""Dashboard business logic extracted from routes/dashboard.py."""

from __future__ import annotations

from datetime import datetime, timedelta, time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.user_model import AuditLog, Organization, RefreshToken, User
from services.auth import RefreshTokenService
from services.sessions import UserSessionService
from services.users import UserService
from services.users.role_scope import filter_users_for_viewer
from utils.datetime_utc import utc_now
from utils.loggers import api_logger, auth_logger


class UserDashboardService:
    @staticmethod
    def get_user_dashboard_overview(
            current_user: User,
            db: Session,
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

            # Get active session count
            sessions = RefreshTokenService.get_user_tokens(db, current_user.id)
            active_sessions = [s for s in sessions if not s.is_revoked]
        
            # Get last login from user record or audit logs
            last_login = current_user.last_login
            if not last_login:
                audit_entry = (
                    db.query(AuditLog)
                    .filter(
                        AuditLog.user_id == current_user.id,
                        AuditLog.action == "login",
                    )
                    .order_by(AuditLog.created_at.desc())
                    .first()
                )
                if audit_entry:
                    last_login = audit_entry.created_at

            org = (
                db.query(Organization).filter(Organization.id == current_user.organization_id).first()
                if current_user.organization_id
                else None
            )

            return {
                "profile": {
                    "username": current_user.username,
                    "email": current_user.email,
                    "role": current_user.role,
                    "status": current_user.status,
                    "organization_id": current_user.organization_id,
                    "organization_name": org.name if org else None,
                    "phone_number": current_user.phone_number,
                    "is_2fa_enabled": getattr(current_user, "is_2fa_enabled", False),
                    "failed_login_attempts": getattr(current_user, "failed_login_attempts", 0),
                },
                "active_sessions": len(active_sessions),
                "last_login": last_login.isoformat() if last_login else None,
                "account_created": current_user.created_at.isoformat() if current_user.created_at else None,
            }
        
        except HTTPException:
            raise
        except Exception as e:
            api_logger.error(
                f"User dashboard overview error: {str(e)}",
                user_id=current_user.id,
                error=str(e),
                event_type="user_dashboard_error"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            )

    @staticmethod
    def get_user_activity(
            current_user: User,
            db: Session,
        limit: int = 20,
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

            # Get audit logs for this user
            from sqlalchemy import and_
            from datetime import datetime, timedelta
        
            now = utc_now()
            today_start = datetime(now.year, now.month, now.day)
            week_ago = now - timedelta(days=7)
            month_ago = now - timedelta(days=30)
        
            # Recent activity (last 20 logs)
            recent_activity = db.query(AuditLog).filter(
                AuditLog.user_id == current_user.id
            ).order_by(
                AuditLog.created_at.desc()
            ).limit(limit).all()
        
            # Login statistics
            logins_today = db.query(AuditLog).filter(
                and_(
                    AuditLog.user_id == current_user.id,
                    AuditLog.action == "login",
                    AuditLog.created_at >= today_start
                )
            ).count()
        
            logins_this_week = db.query(AuditLog).filter(
                and_(
                    AuditLog.user_id == current_user.id,
                    AuditLog.action == "login",
                    AuditLog.created_at >= week_ago
                )
            ).count()
        
            logins_this_month = db.query(AuditLog).filter(
                and_(
                    AuditLog.user_id == current_user.id,
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
                user_id=current_user.id,
                error=str(e),
                event_type="user_activity_error"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            )

    @staticmethod
    def get_user_sessions_dashboard(
            current_user: User,
            db: Session,
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

            # Get user's active sessions
            sessions = RefreshTokenService.get_user_tokens(db, current_user.id)
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
                user_id=current_user.id,
                error=str(e),
                event_type="user_sessions_dashboard_error"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            )
