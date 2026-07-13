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


class AdminDashboardService:
    @staticmethod
    def get_admin_dashboard_overview(
            current_user: User,
            db: Session,
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
        
            org_id = current_user.organization_id
        
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
            today = utc_now().date()
            today_start = datetime.combine(today, time.min)
            tomorrow_start = today_start + timedelta(days=1)
        
            # Today's logins (manageable users only)
            logins_query = db.query(AuditLog).filter(
                AuditLog.action == "login",
                AuditLog.status == "success",
                AuditLog.created_at >= today_start,
                AuditLog.created_at < tomorrow_start,
            )
            if viewable_user_ids:
                logins_query = logins_query.filter(AuditLog.user_id.in_(viewable_user_ids))
            else:
                logins_query = logins_query.filter(False)
            logins_today = logins_query.count()
        
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
                user_id=current_user.id,
                error=str(e),
                event_type="admin_dashboard_error"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            )

    @staticmethod
    def get_admin_users_stats(
            current_user: User,
            db: Session,
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
        
            org_id = current_user.organization_id
        
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
                user_id=current_user.id,
                error=str(e),
                event_type="admin_users_stats_error"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            )

    @staticmethod
    def get_admin_activity_stats(
            current_user: User,
            db: Session,
        limit: int = 20,
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
        
            org_id = current_user.organization_id
        
            viewable_user_ids = [
                u.id
                for u in filter_users_for_viewer(db.query(User), "admin", org_id).all()
            ]
        
            # Get today's activity
            today = utc_now().date()
            today_start = datetime.combine(today, time.min)
            tomorrow_start = today_start + timedelta(days=1)
        
            # Total activity today (manageable users only)
            activity_base = db.query(AuditLog)
            if viewable_user_ids:
                activity_base = activity_base.filter(AuditLog.user_id.in_(viewable_user_ids))
            else:
                activity_base = activity_base.filter(False)
        
            total_activity_today = activity_base.filter(
                AuditLog.created_at >= today_start,
                AuditLog.created_at < tomorrow_start
            ).count()
        
            # Activity by type
            from sqlalchemy import func
            activity_by_type_query = db.query(
                AuditLog.action,
                func.count(AuditLog.id)
            )
            if viewable_user_ids:
                activity_by_type_query = activity_by_type_query.filter(
                    AuditLog.user_id.in_(viewable_user_ids)
                )
            else:
                activity_by_type_query = activity_by_type_query.filter(False)
            activity_by_type = activity_by_type_query.filter(
                AuditLog.created_at >= today_start,
                AuditLog.created_at < tomorrow_start
            ).group_by(AuditLog.action).all()
        
            # Convert to dictionary
            activity_dict = {}
            for action, count in activity_by_type:
                activity_dict[action or "unknown"] = count
        
            # Recent activity (manageable users only)
            recent_activity_query = db.query(AuditLog)
            if viewable_user_ids:
                recent_activity_query = recent_activity_query.filter(
                    AuditLog.user_id.in_(viewable_user_ids)
                )
            else:
                recent_activity_query = recent_activity_query.filter(False)
            recent_activity = recent_activity_query.order_by(
                AuditLog.created_at.desc()
            ).limit(limit).all()
        
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
                user_id=current_user.id,
                error=str(e),
                event_type="admin_activity_stats_error"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            )
