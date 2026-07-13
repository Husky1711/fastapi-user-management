"""Centralized retention / cleanup jobs for durable auth tables."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

from sqlalchemy.orm import Session

from models.user_model import (
    AuditLog,
    EmailVerificationToken,
    LoginAttempt,
    PasswordHistory,
    PasswordResetToken,
    UserInvitation,
)
from services.auth.refresh_token_service import RefreshTokenService
from services.permissions.api_key_service import ApiKeyService
from services.permissions.user_permission_service import UserPermissionService
from services.sessions.user_session_service import UserSessionService
from utils.datetime_utc import utc_now
from utils.loggers import auth_logger


class RetentionService:
    """Run periodic purge jobs that would otherwise rely on manual endpoints only."""

    @staticmethod
    def cleanup_password_history(db: Session) -> Dict[str, Any]:
        """Purge history rows older than retention days (keeps recent per-user via age only)."""
        from services.core.data_retention_policy_service import DataRetentionPolicyService

        days = DataRetentionPolicyService.get_retention_days(db, "password_history")
        if days is None:
            return {"deleted": 0, "skipped": True, "reason": "policy_inactive"}
        cutoff = utc_now() - timedelta(days=days)
        deleted = (
            db.query(PasswordHistory)
            .filter(PasswordHistory.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        return {"deleted": deleted, "older_than_days": days}

    @staticmethod
    def cleanup_password_reset_tokens(db: Session) -> Dict[str, Any]:
        cutoff = utc_now()
        deleted = (
            db.query(PasswordResetToken)
            .filter(
                (PasswordResetToken.used_at.isnot(None))
                | (PasswordResetToken.expires_at < cutoff)
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        return {"deleted": deleted}

    @staticmethod
    def cleanup_email_verification_tokens(db: Session) -> Dict[str, Any]:
        cutoff = utc_now()
        deleted = (
            db.query(EmailVerificationToken)
            .filter(
                (EmailVerificationToken.verified_at.isnot(None))
                | (EmailVerificationToken.expires_at < cutoff)
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        return {"deleted": deleted}

    @staticmethod
    def cleanup_invitations(db: Session) -> Dict[str, Any]:
        from services.core.data_retention_policy_service import DataRetentionPolicyService

        days = DataRetentionPolicyService.get_retention_days(db, "user_invitations")
        if days is None:
            return {"deleted": 0, "skipped": True, "reason": "policy_inactive"}
        cutoff = utc_now() - timedelta(days=days)
        deleted = (
            db.query(UserInvitation)
            .filter(UserInvitation.expires_at < cutoff)
            .filter(
                (UserInvitation.accepted_at.isnot(None))
                | (UserInvitation.revoked_at.isnot(None))
                | (UserInvitation.expires_at < utc_now())
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        return {"deleted": deleted, "older_than_days": days}

    @staticmethod
    def cleanup_login_attempts(db: Session) -> Dict[str, Any]:
        from services.core.data_retention_policy_service import DataRetentionPolicyService

        days = DataRetentionPolicyService.get_retention_days(db, "login_attempts")
        if days is None:
            return {"deleted": 0, "skipped": True, "reason": "policy_inactive"}
        cutoff = utc_now() - timedelta(days=days)
        deleted = (
            db.query(LoginAttempt)
            .filter(LoginAttempt.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        return {"deleted": deleted, "older_than_days": days}

    @staticmethod
    def cleanup_audit_logs(db: Session) -> Dict[str, Any]:
        """Age-based purge until monthly partitioning is introduced."""
        from services.core.data_retention_policy_service import DataRetentionPolicyService

        days = DataRetentionPolicyService.get_retention_days(db, "audit_logs")
        if days is None:
            return {"deleted": 0, "skipped": True, "reason": "policy_inactive"}
        cutoff = utc_now() - timedelta(days=days)
        deleted = (
            db.query(AuditLog)
            .filter(AuditLog.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        return {"deleted": deleted, "older_than_days": days}

    @staticmethod
    def run_all(db: Session) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        try:
            results["sessions"] = UserSessionService.cleanup_expired_sessions(db=db)
        except Exception as exc:
            results["sessions"] = {"success": False, "error": str(exc)}

        try:
            results["refresh_tokens_deleted"] = RefreshTokenService.cleanup_expired_tokens(db)
        except Exception as exc:
            results["refresh_tokens"] = {"success": False, "error": str(exc)}

        try:
            results["password_history"] = RetentionService.cleanup_password_history(db)
        except Exception as exc:
            results["password_history"] = {"success": False, "error": str(exc)}

        try:
            results["permissions"] = UserPermissionService.cleanup_expired_permissions(db)
        except Exception as exc:
            results["permissions"] = {"success": False, "error": str(exc)}

        try:
            results["api_keys"] = ApiKeyService.cleanup_expired_api_keys(db)
        except Exception as exc:
            results["api_keys"] = {"success": False, "error": str(exc)}

        try:
            results["password_reset_tokens"] = RetentionService.cleanup_password_reset_tokens(db)
        except Exception as exc:
            results["password_reset_tokens"] = {"success": False, "error": str(exc)}

        try:
            results["email_verification_tokens"] = (
                RetentionService.cleanup_email_verification_tokens(db)
            )
        except Exception as exc:
            results["email_verification_tokens"] = {"success": False, "error": str(exc)}

        try:
            results["invitations"] = RetentionService.cleanup_invitations(db)
        except Exception as exc:
            results["invitations"] = {"success": False, "error": str(exc)}

        try:
            results["login_attempts"] = RetentionService.cleanup_login_attempts(db)
        except Exception as exc:
            results["login_attempts"] = {"success": False, "error": str(exc)}

        try:
            results["audit_logs"] = RetentionService.cleanup_audit_logs(db)
        except Exception as exc:
            results["audit_logs"] = {"success": False, "error": str(exc)}

        auth_logger.info(
            "Retention cleanup completed",
            event_type="retention_cleanup",
            results={k: (v if not isinstance(v, dict) else {**v}) for k, v in results.items()},
        )
        return {"success": True, "results": results}
