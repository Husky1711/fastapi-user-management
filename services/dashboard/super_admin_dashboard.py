"""Dashboard business logic extracted from routes/dashboard.py."""

from __future__ import annotations

from datetime import datetime, timedelta, time

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.user_model import AuditLog, Organization, RefreshToken, User
from services.dashboard.cache import cached_dashboard, dashboard_cache_key
from utils.datetime_utc import utc_now
from utils.loggers import api_logger


class SuperAdminDashboardService:
    @staticmethod
    def get_super_admin_overview(
        current_user: User,
        db: Session,
    ):
        """
        Get super admin's system-wide overview

        **Returns:**
        - Total organizations, users, admins, sessions
        - Active sessions count
        - Today's statistics
        """
        try:

            def _build():
                all_users = db.query(User).filter(User.deleted_at.is_(None)).all()
                total_users = len(all_users)

                super_admin_count = len([u for u in all_users if u.role == "super_admin"])
                org_admin_count = len(
                    [u for u in all_users if u.role == "organization_admin"]
                )
                admin_count = len([u for u in all_users if u.role == "admin"])
                user_count = len([u for u in all_users if u.role == "user"])
                active_users = len([u for u in all_users if u.status == "active"])

                all_sessions = (
                    db.query(RefreshToken).filter(RefreshToken.is_revoked == False).all()
                )
                active_sessions = len(all_sessions)
                total_sessions = db.query(RefreshToken).count()

                org_ids = db.query(User.organization_id).distinct().all()
                total_organizations = len(
                    [org[0] for org in org_ids if org[0] is not None]
                )

                today = utc_now().date()
                today_start = datetime.combine(today, time.min)
                tomorrow_start = today_start + timedelta(days=1)

                total_audit_logs_today = (
                    db.query(AuditLog)
                    .filter(
                        AuditLog.created_at >= today_start,
                        AuditLog.created_at < tomorrow_start,
                    )
                    .count()
                )

                logins_today = (
                    db.query(AuditLog)
                    .filter(
                        AuditLog.action == "login",
                        AuditLog.status == "success",
                        AuditLog.created_at >= today_start,
                        AuditLog.created_at < tomorrow_start,
                    )
                    .count()
                )

                new_users_today = (
                    db.query(User)
                    .filter(
                        User.created_at >= today_start,
                        User.created_at < tomorrow_start,
                    )
                    .count()
                )

                return {
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
                        "user": user_count,
                    },
                    "today_stats": {
                        "logins": logins_today,
                        "new_users": new_users_today,
                        "total_audit_logs": total_audit_logs_today,
                    },
                }

            return cached_dashboard(
                dashboard_cache_key("super_admin", "overview"), _build
            )

        except HTTPException:
            raise
        except Exception as e:
            api_logger.error(
                f"Super admin dashboard overview error: {str(e)}",
                user_id=current_user.id,
                error=str(e),
                event_type="super_admin_dashboard_error",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )

    @staticmethod
    def get_super_admin_users_stats(
        current_user: User,
        db: Session,
    ):
        """System-wide user statistics (cached 60s)."""
        try:

            def _build():
                all_users = db.query(User).filter(User.deleted_at.is_(None)).all()

                super_admin_count = len([u for u in all_users if u.role == "super_admin"])
                org_admin_count = len(
                    [u for u in all_users if u.role == "organization_admin"]
                )
                admin_count = len([u for u in all_users if u.role == "admin"])
                user_count = len([u for u in all_users if u.role == "user"])

                active_count = len([u for u in all_users if u.status == "active"])
                inactive_count = len([u for u in all_users if u.status == "inactive"])
                locked_count = len([u for u in all_users if u.status == "locked"])

                today = utc_now().date()
                week_ago = today - timedelta(days=7)
                month_ago = today - timedelta(days=30)

                today_start = datetime.combine(today, time.min)
                week_start = datetime.combine(week_ago, time.min)
                month_start = datetime.combine(month_ago, time.min)
                tomorrow_start = today_start + timedelta(days=1)

                users_today = (
                    db.query(User)
                    .filter(
                        User.created_at >= today_start,
                        User.created_at < tomorrow_start,
                    )
                    .count()
                )
                users_this_week = (
                    db.query(User).filter(User.created_at >= week_start).count()
                )
                users_this_month = (
                    db.query(User).filter(User.created_at >= month_start).count()
                )

                recent_users = (
                    db.query(User).order_by(User.created_at.desc()).limit(20).all()
                )
                recent_users_list = [
                    {
                        "id": u.id,
                        "username": u.username,
                        "email": u.email,
                        "role": u.role,
                        "status": u.status,
                        "organization_id": u.organization_id,
                        "created_at": u.created_at.isoformat() if u.created_at else None,
                    }
                    for u in recent_users
                ]

                return {
                    "total_users": len(all_users),
                    "active_users": active_count,
                    "locked_users": locked_count,
                    "users_by_role": {
                        "super_admin": super_admin_count,
                        "organization_admin": org_admin_count,
                        "admin": admin_count,
                        "user": user_count,
                    },
                    "users_by_status": {
                        "active": active_count,
                        "inactive": inactive_count,
                        "locked": locked_count,
                    },
                    "users_today": users_today,
                    "users_this_week": users_this_week,
                    "users_this_month": users_this_month,
                    "recent_users": recent_users_list,
                }

            return cached_dashboard(
                dashboard_cache_key("super_admin", "users_stats"), _build
            )

        except HTTPException:
            raise
        except Exception as e:
            api_logger.error(
                f"Super admin users stats error: {str(e)}",
                user_id=current_user.id,
                error=str(e),
                event_type="super_admin_users_stats_error",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )

    @staticmethod
    def get_super_admin_organizations_stats(
        current_user: User,
        db: Session,
    ):
        """Organization statistics across the system (cached 60s)."""
        try:

            def _build():
                org_ids = db.query(User.organization_id).distinct().all()
                all_org_ids = [org[0] for org in org_ids if org[0] is not None]
                total_organizations = len(all_org_ids)

                small_orgs = 0
                medium_orgs = 0
                large_orgs = 0

                for org_id in all_org_ids:
                    user_count = (
                        db.query(User).filter(User.organization_id == org_id).count()
                    )
                    if user_count < 10:
                        small_orgs += 1
                    elif user_count <= 100:
                        medium_orgs += 1
                    else:
                        large_orgs += 1

                active_orgs = 0
                organizations_list = []
                for org_id in all_org_ids:
                    org = (
                        db.query(Organization).filter(Organization.id == org_id).first()
                    )
                    user_count = (
                        db.query(User).filter(User.organization_id == org_id).count()
                    )
                    active_users = (
                        db.query(User)
                        .filter(
                            User.organization_id == org_id,
                            User.status == "active",
                        )
                        .count()
                    )
                    if active_users > 0:
                        active_orgs += 1
                    organizations_list.append(
                        {
                            "id": org_id,
                            "name": org.name if org else f"Organization {org_id}",
                            "status": org.status if org else "unknown",
                            "total_users": user_count,
                            "active_users": active_users,
                        }
                    )

                organizations_list.sort(key=lambda item: item["id"])

                return {
                    "total_organizations": total_organizations,
                    "active_organizations": active_orgs,
                    "inactive_organizations": total_organizations - active_orgs,
                    "organizations_by_size": {
                        "small": small_orgs,
                        "medium": medium_orgs,
                        "large": large_orgs,
                    },
                    "organizations": organizations_list,
                }

            return cached_dashboard(
                dashboard_cache_key("super_admin", "organizations_stats"), _build
            )

        except HTTPException:
            raise
        except Exception as e:
            api_logger.error(
                f"Super admin organizations stats error: {str(e)}",
                user_id=current_user.id,
                error=str(e),
                event_type="super_admin_orgs_stats_error",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )

    @staticmethod
    def get_super_admin_sessions_stats(
        current_user: User,
        db: Session,
    ):
        """System-wide session statistics (cached 60s)."""
        try:

            def _build():
                all_sessions = db.query(RefreshToken).all()
                total_sessions = len(all_sessions)
                active_sessions = len([s for s in all_sessions if not s.is_revoked])
                revoked_sessions = total_sessions - active_sessions

                recent_sessions = (
                    db.query(RefreshToken)
                    .order_by(RefreshToken.created_at.desc())
                    .limit(30)
                    .all()
                )
                recent_sessions_list = [
                    {
                        "id": s.id,
                        "user_id": s.user_id,
                        "device_info": s.device_info or "Unknown",
                        "created_at": s.created_at.isoformat() if s.created_at else None,
                        "is_revoked": s.is_revoked,
                    }
                    for s in recent_sessions
                ]

                return {
                    "total_sessions": total_sessions,
                    "active_sessions": active_sessions,
                    "revoked_sessions": revoked_sessions,
                    "recent_sessions": recent_sessions_list,
                }

            return cached_dashboard(
                dashboard_cache_key("super_admin", "sessions_stats"), _build
            )

        except HTTPException:
            raise
        except Exception as e:
            api_logger.error(
                f"Super admin sessions stats error: {str(e)}",
                user_id=current_user.id,
                error=str(e),
                event_type="super_admin_sessions_stats_error",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )
