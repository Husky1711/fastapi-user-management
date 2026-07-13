"""Two-step login flow when 2FA is enabled."""

from __future__ import annotations

import json
import secrets
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from models.user_model import User
from services.audit import AuditLogService
from services.auth.auth_service import AuthService
from services.auth.two_factor_secret_service import TwoFactorSecretService
from services.auth.two_factor_service import TwoFactorService
from services.users import UserService
from utils.datetime_utc import utc_now
from utils.loggers import auth_logger
from utils.redis_config import RedisClient

_CHALLENGE_TTL_SECONDS = 300
_CHALLENGE_PREFIX = "login_2fa:"


class Login2FAService:
    @staticmethod
    def requires_2fa(user: User) -> bool:
        """True when the user has enrolled TOTP/backup 2FA."""
        return bool(user.is_2fa_enabled and user.two_factor_secret)

    @staticmethod
    def enrollment_required(db: Session, user: User) -> bool:
        """Org mandates 2FA but user has not enrolled yet."""
        if Login2FAService.requires_2fa(user):
            return False
        try:
            from services.users.organization_settings_service import (
                OrganizationSettingsService,
            )

            return bool(
                OrganizationSettingsService.get_setting(
                    db, user.organization_id, "require_2fa", default=False
                )
            )
        except Exception:
            return False

    @staticmethod
    def create_challenge(
        user_id: int,
        ip_address: str,
        user_agent: str,
        device_info: str,
    ) -> str:
        challenge_token = secrets.token_urlsafe(32)
        payload = {
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "device_info": device_info,
            "created_at": utc_now().isoformat(),
        }
        RedisClient.get_client().setex(
            f"{_CHALLENGE_PREFIX}{challenge_token}",
            _CHALLENGE_TTL_SECONDS,
            json.dumps(payload),
        )
        return challenge_token

    @staticmethod
    def build_challenge_response(challenge_token: str) -> Dict[str, Any]:
        return {
            "requires_2fa": True,
            "challenge_token": challenge_token,
            "message": "Two-factor authentication required",
        }

    @staticmethod
    def _load_challenge(challenge_token: str) -> Optional[Dict[str, Any]]:
        raw = RedisClient.get_client().get(f"{_CHALLENGE_PREFIX}{challenge_token}")
        if not raw:
            return None
        return json.loads(raw)

    @staticmethod
    def _delete_challenge(challenge_token: str) -> None:
        RedisClient.get_client().delete(f"{_CHALLENGE_PREFIX}{challenge_token}")

    @staticmethod
    def verify_user_code(db: Session, user: User, code: str) -> bool:
        secret = TwoFactorSecretService.decrypt(user.two_factor_secret)
        if not secret:
            return False

        normalized = code.strip().upper()
        if TwoFactorService.verify_totp(secret, normalized):
            return True

        if user.backup_codes and TwoFactorService.verify_backup_code(
            normalized, user.backup_codes
        ):
            used_hash = TwoFactorService.hash_backup_codes([normalized])[0]
            user.backup_codes = [
                hashed for hashed in user.backup_codes if hashed != used_hash
            ]
            db.commit()
            return True

        return False

    @staticmethod
    def complete_login(
        db: Session,
        challenge_token: str,
        totp_code: str,
        correlation_id: Optional[str] = None,
    ) -> Tuple[Optional[User], Optional[str], Optional[str], Optional[str]]:
        """
        Verify challenge + TOTP and issue tokens.

        Returns (user, access_token, refresh_token, error_message).
        """
        challenge = Login2FAService._load_challenge(challenge_token)
        if not challenge:
            return None, None, None, "Invalid or expired 2FA challenge"

        user = UserService.get_user_by_id(db, challenge["user_id"])
        if not user or not Login2FAService.requires_2fa(user):
            Login2FAService._delete_challenge(challenge_token)
            return None, None, None, "Invalid or expired 2FA challenge"

        if not Login2FAService.verify_user_code(db, user, totp_code):
            auth_logger.warning(
                "2FA login verification failed",
                user_id=user.id,
                event_type="login_2fa_failed",
            )
            return None, None, None, "Invalid 2FA code"

        Login2FAService._delete_challenge(challenge_token)

        access_token, refresh_token = AuthService.create_tokens_for_user(
            db,
            user,
            challenge.get("device_info"),
            challenge.get("ip_address"),
            challenge.get("user_agent"),
        )
        UserService.update_last_login(db, user.id)

        auth_logger.login_success(
            user_id=user.id,
            username=user.username,
            ip_address=challenge.get("ip_address", "Unknown"),
            duration_ms=0,
            user_agent=challenge.get("user_agent", "Unknown"),
            correlation_id=correlation_id,
        )
        AuditLogService.log_authentication_event(
            db=db,
            event_type="login",
            user_id=user.id,
            username=user.username,
            email=user.email,
            ip_address=challenge.get("ip_address"),
            user_agent=challenge.get("user_agent"),
            request_id=correlation_id,
            correlation_id=correlation_id,
            status="success",
            metadata={"token_type": "access_refresh", "2fa_verified": True},
        )

        return user, access_token, refresh_token, None
