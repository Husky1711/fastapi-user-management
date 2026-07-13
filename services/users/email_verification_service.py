"""Email verification token service."""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from config.settings import settings
from models.user_model import EmailVerificationToken, User
from utils.datetime_utc import utc_now
from utils.loggers import auth_logger

VERIFY_TOKEN_TTL_HOURS = 24


class EmailVerificationService:
    @staticmethod
    def generate_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def issue_token(db: Session, user: User, email: Optional[str] = None) -> Dict[str, Any]:
        """Create a durable verification token; return plaintext once."""
        target_email = email or user.email

        (
            db.query(EmailVerificationToken)
            .filter(EmailVerificationToken.user_id == user.id)
            .filter(EmailVerificationToken.verified_at.is_(None))
            .update(
                {EmailVerificationToken.verified_at: utc_now()},
                synchronize_session=False,
            )
        )

        raw = EmailVerificationService.generate_token()
        expires_at = utc_now() + timedelta(hours=VERIFY_TOKEN_TTL_HOURS)
        row = EmailVerificationToken(
            user_id=user.id,
            email=target_email,
            token_hash=EmailVerificationService._hash_token(raw),
            expires_at=expires_at,
        )
        db.add(row)
        db.commit()

        auth_logger.info(
            f"Email verification token issued for {user.username}",
            user_id=user.id,
            email=target_email,
            event_type="email_verification_issued",
        )

        response: Dict[str, Any] = {
            "success": True,
            "expires_in_hours": VERIFY_TOKEN_TTL_HOURS,
            "email": target_email,
            "_token": raw,
        }
        if settings.is_development():
            response["verification_token"] = raw
        return response

    @staticmethod
    def send_verification_email(user: User, token: str) -> None:
        if not settings.email.enable_emails:
            return
        try:
            from utils.email_service import get_email_service

            get_email_service().send_verification_email(
                to_email=user.email,
                verification_token=token,
                username=user.username,
            )
        except Exception as email_error:
            auth_logger.error(
                f"Failed to send verification email: {email_error}",
                user_id=user.id,
                email=user.email,
                error=str(email_error),
                event_type="email_verification_send_error",
            )

    @staticmethod
    def verify_token(db: Session, token: str) -> Dict[str, Any]:
        token_hash = EmailVerificationService._hash_token(token)
        row = (
            db.query(EmailVerificationToken)
            .filter(EmailVerificationToken.token_hash == token_hash)
            .filter(EmailVerificationToken.verified_at.is_(None))
            .filter(EmailVerificationToken.expires_at > utc_now())
            .first()
        )
        if not row:
            return {"success": False, "error": "Invalid or expired verification token"}

        user = db.query(User).filter(User.id == row.user_id).first()
        if not user:
            return {"success": False, "error": "User not found"}

        now = utc_now()
        row.verified_at = now
        user.email = row.email
        user.email_verified_at = now
        user.updated_at = now
        db.commit()

        auth_logger.info(
            f"Email verified for {user.username}",
            user_id=user.id,
            email=user.email,
            event_type="email_verified",
        )
        return {
            "success": True,
            "message": "Email verified successfully",
            "user_id": user.id,
            "email": user.email,
        }

    @staticmethod
    def resend_for_email(db: Session, email: str) -> Dict[str, Any]:
        """Issue a new token if the email exists and is unverified (no enumeration)."""
        generic = {
            "success": True,
            "message": "If the account exists and is unverified, a verification email was sent",
            "expires_in_hours": VERIFY_TOKEN_TTL_HOURS,
        }
        user = db.query(User).filter(User.email == email).first()
        if not user or user.email_verified_at is not None:
            return generic

        issued = EmailVerificationService.issue_token(db, user)
        EmailVerificationService.send_verification_email(user, issued["_token"])
        if settings.is_development():
            generic["verification_token"] = issued["_token"]
        return generic
