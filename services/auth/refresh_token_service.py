from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List
from config.settings import settings
from models.user_model import RefreshToken, User
from services.sessions import UserSessionService
from utils.datetime_utc import utc_now
from utils.jwt_config import hash_token
import secrets


class RefreshTokenService:
    @staticmethod
    def create_refresh_token(
        db: Session,
        user: User,
        device_info: str = None,
        ip_address: str = None,
        user_agent: str = None,
    ) -> tuple[str, RefreshToken]:
        """Create a new refresh token (auth session; link user_sessions separately)."""
        token = secrets.token_urlsafe(32)

        token_hash = hash_token(token)
        expires_at = utc_now() + timedelta(days=settings.jwt.refresh_token_expire_days)

        db_refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        db.add(db_refresh_token)
        db.commit()
        db.refresh(db_refresh_token)

        return token, db_refresh_token

    @staticmethod
    def verify_refresh_token(db: Session, token: str) -> Optional[User]:
        """Verify a refresh token and return the user.

        If a revoked token hash is presented again, treat as reuse:
        revoke all of that user's sessions and return None.
        """
        token_hash = hash_token(token)

        db_token = db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > utc_now(),
        ).first()

        if db_token:
            user = db.query(User).filter(User.id == db_token.user_id).first()
            # Soft-deleted users must not refresh even if a token row survived.
            if user is None or getattr(user, "deleted_at", None) is not None:
                return None
            return user

        reused = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.token_hash == token_hash,
                RefreshToken.is_revoked == True,
            )
            .first()
        )
        if reused:
            RefreshTokenService.revoke_all_user_tokens(
                db, reused.user_id, reason="refresh_reuse_detected"
            )
            try:
                from services.core.consent_incident_service import SecurityIncidentService
                from utils.metrics import metrics

                metrics.inc_refresh_reuse()
                SecurityIncidentService.record(
                    db,
                    incident_type="refresh_token_reuse",
                    user_id=reused.user_id,
                    severity="high",
                    details={
                        "reason": "refresh_reuse_detected",
                        "refresh_token_id": reused.id,
                    },
                )
            except Exception:
                pass
        return None

    @staticmethod
    def revoke_token_by_id(db: Session, token_id: int, reason: str = "revoke") -> bool:
        """Revoke a refresh token by database id and deactivate linked analytics sessions."""
        db_token = (
            db.query(RefreshToken)
            .filter(RefreshToken.id == token_id, RefreshToken.is_revoked == False)
            .first()
        )

        if not db_token:
            return False

        db_token.is_revoked = True
        db_token.revoked_at = utc_now()
        db.commit()

        UserSessionService.deactivate_by_refresh_token_id(db, token_id, reason=reason)
        return True

    @staticmethod
    def revoke_token(db: Session, token: str, reason: str = "logout") -> bool:
        """Revoke a refresh token by raw token value."""
        token_hash = hash_token(token)

        db_token = (
            db.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash, RefreshToken.is_revoked == False)
            .first()
        )

        if not db_token:
            return False

        return RefreshTokenService.revoke_token_by_id(db, db_token.id, reason=reason)

    @staticmethod
    def revoke_all_user_tokens(
        db: Session,
        user_id: int,
        reason: str = "revoke_all",
        *,
        commit: bool = True,
    ) -> int:
        """Revoke all refresh tokens for a user and linked analytics sessions."""
        active_tokens = (
            db.query(RefreshToken)
            .filter(RefreshToken.user_id == user_id, RefreshToken.is_revoked == False)
            .all()
        )
        token_ids = [token.id for token in active_tokens]

        if not token_ids:
            return 0

        db.query(RefreshToken).filter(RefreshToken.id.in_(token_ids)).update(
            {
                "is_revoked": True,
                "revoked_at": utc_now(),
            },
            synchronize_session=False,
        )
        if commit:
            db.commit()
            UserSessionService.deactivate_by_refresh_token_ids(
                db, token_ids, reason=reason, commit=True
            )
        else:
            UserSessionService.deactivate_by_refresh_token_ids(
                db, token_ids, reason=reason, commit=False
            )
        return len(token_ids)

    @staticmethod
    def get_active_token_for_user(
        db: Session, user_id: int, token: str
    ) -> Optional[RefreshToken]:
        """Look up an active refresh token row for a user by raw token value."""
        token_hash = hash_token(token)
        return (
            db.query(RefreshToken)
            .filter(
                RefreshToken.user_id == user_id,
                RefreshToken.token_hash == token_hash,
                RefreshToken.is_revoked == False,
                RefreshToken.expires_at > utc_now(),
            )
            .first()
        )

    @staticmethod
    def get_user_tokens(db: Session, user_id: int) -> List[RefreshToken]:
        """Get all active refresh tokens for a user"""
        return (
            db.query(RefreshToken)
            .filter(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False,
                RefreshToken.expires_at > utc_now(),
            )
            .all()
        )

    @staticmethod
    def cleanup_expired_tokens(db: Session) -> int:
        """Clean up expired refresh tokens"""
        count = db.query(RefreshToken).filter(RefreshToken.expires_at < utc_now()).delete()

        db.commit()
        return count

    @staticmethod
    def rotate_token(
        db: Session,
        old_token: str,
        user: User,
        device_info: str = None,
        ip_address: str = None,
        user_agent: str = None,
        access_token: str | None = None,
    ) -> tuple[str, RefreshToken]:
        """Rotate refresh token (revoke old, create new, re-link analytics session)."""
        RefreshTokenService.revoke_token(db, old_token, reason="token_rotation")

        new_token, db_refresh_token = RefreshTokenService.create_refresh_token(
            db, user, device_info, ip_address, user_agent
        )

        if access_token:
            UserSessionService.create_for_refresh_token(
                db=db,
                user_id=user.id,
                refresh_token_row=db_refresh_token,
                access_token=access_token,
                user_agent=user_agent or device_info,
                ip_address=ip_address,
            )

        return new_token, db_refresh_token
