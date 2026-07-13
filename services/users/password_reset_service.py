from sqlalchemy.orm import Session
from models.user_model import User, PasswordResetToken
from utils.datetime_utc import utc_now
from typing import Optional, Dict, Any
from datetime import timedelta
from utils.jwt_config import get_password_hash
import secrets
import hashlib
import json
from utils.loggers import auth_logger
from utils.redis_config import RedisClient
from .password_history_service import PasswordHistoryService
from .user_service import UserService
from config.settings import settings

RESET_TOKEN_TTL_MINUTES = 15
RESET_TOKEN_TTL_SECONDS = RESET_TOKEN_TTL_MINUTES * 60


class PasswordResetService:
    """Password reset using durable hashed tokens (Redis is optional cache)."""

    @staticmethod
    def generate_reset_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _cache_set(token: str, user_id: int, email: str, expires_at_iso: str) -> None:
        try:
            redis_client = RedisClient.get_client()
            redis_client.setex(
                f"password_reset:{token}",
                RESET_TOKEN_TTL_SECONDS,
                json.dumps(
                    {
                        "user_id": user_id,
                        "email": email,
                        "expires_at": expires_at_iso,
                    }
                ),
            )
        except Exception as cache_error:
            auth_logger.warning(
                f"Password reset Redis cache write failed: {cache_error}",
                event_type="password_reset_cache_write_error",
            )

    @staticmethod
    def _cache_delete(token: str) -> None:
        try:
            RedisClient.get_client().delete(f"password_reset:{token}")
        except Exception:
            pass

    @staticmethod
    def _get_active_token_row(db: Session, token: str) -> Optional[PasswordResetToken]:
        token_hash = PasswordResetService._hash_token(token)
        # utc_now() is naive UTC; MySQL DATETIME columns are naive.
        return (
            db.query(PasswordResetToken)
            .filter(PasswordResetToken.token_hash == token_hash)
            .filter(PasswordResetToken.used_at.is_(None))
            .filter(PasswordResetToken.expires_at > utc_now())
            .first()
        )

    @staticmethod
    def request_password_reset(
        db: Session,
        email: str,
        requested_ip: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            user = UserService.get_user_by_email(db, email)
            if not user:
                return {
                    "success": True,
                    "message": "If the email exists, a password reset link has been sent",
                    "reset_token": None,
                    "expires_in_minutes": RESET_TOKEN_TTL_MINUTES,
                }

            # Invalidate unused prior tokens for this user.
            (
                db.query(PasswordResetToken)
                .filter(PasswordResetToken.user_id == user.id)
                .filter(PasswordResetToken.used_at.is_(None))
                .update(
                    {PasswordResetToken.used_at: utc_now()},
                    synchronize_session=False,
                )
            )

            reset_token = PasswordResetService.generate_reset_token()
            expires_at = utc_now() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)
            db.add(
                PasswordResetToken(
                    user_id=user.id,
                    token_hash=PasswordResetService._hash_token(reset_token),
                    expires_at=expires_at,
                    requested_ip=requested_ip,
                )
            )
            db.commit()

            PasswordResetService._cache_set(
                reset_token,
                user.id,
                user.email,
                expires_at.isoformat(),
            )

            try:
                from services.audit.audit_log_service import AuditLogService

                AuditLogService.log_security_event(
                    db=db,
                    event_type="password_reset_requested",
                    user_id=user.id,
                    organization_id=user.organization_id,
                    ip_address=requested_ip,
                    status="success",
                    metadata={"email": user.email},
                )
            except Exception as audit_error:
                auth_logger.warning(
                    f"Password reset request audit log failed: {audit_error}",
                    user_id=user.id,
                    event_type="password_reset_audit_error",
                )

            auth_logger.info(
                f"Password reset requested for user: {user.username}",
                user_id=user.id,
                username=user.username,
                email=user.email,
                reset_token=reset_token[:8] + "...",
                event_type="password_reset_requested",
            )

            if settings.email.enable_emails:
                try:
                    from utils.email_service import get_email_service

                    get_email_service().send_password_reset_email(
                        to_email=user.email,
                        reset_token=reset_token,
                        username=user.username,
                    )
                except Exception as email_error:
                    auth_logger.error(
                        f"Failed to send password reset email: {str(email_error)}",
                        user_id=user.id,
                        email=user.email,
                        error=str(email_error),
                        event_type="password_reset_email_error",
                    )

            response: Dict[str, Any] = {
                "success": True,
                "message": "Password reset link has been sent to your email",
                "expires_in_minutes": RESET_TOKEN_TTL_MINUTES,
            }
            if settings.is_development():
                response["reset_token"] = reset_token
            return response

        except Exception as e:
            db.rollback()
            auth_logger.error(
                f"Error requesting password reset: {str(e)}",
                email=email,
                error=str(e),
                event_type="password_reset_request_error",
            )
            return {
                "success": False,
                "error": f"Failed to process password reset request: {str(e)}",
            }

    @staticmethod
    def confirm_password_reset(db: Session, token: str, new_password: str) -> Dict[str, Any]:
        try:
            row = PasswordResetService._get_active_token_row(db, token)
            if not row:
                return {
                    "success": False,
                    "error": "Invalid or expired reset token",
                }

            user = UserService.get_user_by_id(db, row.user_id)
            if not user:
                return {
                    "success": False,
                    "error": "User not found",
                }

            if settings.password_policy.enable_password_history:
                reuse_check = PasswordHistoryService.check_password_reuse(
                    db,
                    user.id,
                    new_password,
                    settings.password_policy.password_history_limit,
                )
                if reuse_check.get("is_reused", False):
                    return {
                        "success": False,
                        "error": reuse_check.get(
                            "message", "Cannot reuse recent passwords"
                        ),
                    }
                PasswordHistoryService.save_password_history(
                    db, user.id, user.password_hash, user.id, "password_reset"
                )

            user.password_hash = get_password_hash(new_password)
            user.updated_at = utc_now()
            user.password_changed_at = utc_now()
            row.used_at = utc_now()
            db.commit()
            db.refresh(user)

            PasswordResetService._cache_delete(token)

            try:
                from services.audit.audit_log_service import AuditLogService

                AuditLogService.log_security_event(
                    db=db,
                    event_type="password_reset_completed",
                    user_id=user.id,
                    organization_id=user.organization_id,
                    status="success",
                    metadata={"token_id": row.id},
                )
            except Exception as audit_error:
                auth_logger.warning(
                    f"Password reset completion audit log failed: {audit_error}",
                    user_id=user.id,
                    event_type="password_reset_audit_error",
                )

            auth_logger.info(
                f"Password reset completed for user: {user.username}",
                user_id=user.id,
                username=user.username,
                email=user.email,
                event_type="password_reset_completed",
            )

            return {
                "success": True,
                "message": "Password has been reset successfully",
            }

        except Exception as e:
            db.rollback()
            auth_logger.error(
                f"Error confirming password reset: {str(e)}",
                token=token[:8] + "..." if token else None,
                error=str(e),
                event_type="password_reset_confirm_error",
            )
            return {
                "success": False,
                "error": f"Failed to reset password: {str(e)}",
            }

    @staticmethod
    def validate_reset_token(db: Session, token: str) -> Dict[str, Any]:
        try:
            row = PasswordResetService._get_active_token_row(db, token)
            if not row:
                return {
                    "valid": False,
                    "error": "Invalid or expired reset token",
                }

            user = UserService.get_user_by_id(db, row.user_id)
            return {
                "valid": True,
                "email": user.email if user else None,
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            }

        except Exception as e:
            auth_logger.error(
                f"Error validating reset token: {str(e)}",
                token=token[:8] + "..." if token else None,
                error=str(e),
                event_type="password_reset_validation_error",
            )
            return {
                "valid": False,
                "error": f"Failed to validate token: {str(e)}",
            }
