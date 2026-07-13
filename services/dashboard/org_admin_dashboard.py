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


class OrgAdminDashboardService:
    @staticmethod
    def get_organization_admin_overview(
            current_user: User,
            db: Session,
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

            # Check if user is organization admin
        
            org_id = current_user.organization_id
        
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
            today = utc_now().date()
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
                user_id=current_user.id,
                error=str(e),
                event_type="org_admin_dashboard_error"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            )

    @staticmethod
    def get_organization_admin_users_stats(
            current_user: User,
            db: Session,
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

            # Check if user is organization admin
        
            org_id = current_user.organization_id
        
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
                user_id=current_user.id,
                error=str(e),
                event_type="org_admin_users_stats_error"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            )

    @staticmethod
    def get_organization_admin_sessions_stats(
            current_user: User,
            db: Session,
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

            # Check if user is organization admin
        
            org_id = current_user.organization_id
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
                user_id=current_user.id,
                error=str(e),
                event_type="org_admin_sessions_stats_error"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            )
