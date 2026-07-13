from datetime import datetime, timedelta
from typing import Optional, Tuple

import hashlib
from sqlalchemy.orm import Session

from models.user_model import RefreshToken, User
from services.sessions import UserSessionService
from utils.jwt_config import create_user_token

from .refresh_token_service import RefreshTokenService


class AuthService:
    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        """Authenticate a user with username and password"""
        from services.users import UserService

        return UserService.authenticate_user(db, username, password)

    @staticmethod
    def create_tokens_for_user(
        db: Session,
        user: User,
        device_info: str = None,
        ip_address: str = None,
        user_agent: str = None,
        *,
        track_compliance_session: bool = True,
    ) -> Tuple[str, str]:
        """Create access + refresh tokens; optionally link a user_sessions analytics row."""
        from config.settings import settings

        # Enforce max concurrent auth sessions (revoke oldest before issuing new).
        existing = RefreshTokenService.get_user_tokens(db, user.id)
        max_sessions = settings.session.max_sessions_per_user
        if len(existing) >= max_sessions:
            overflow = len(existing) - max_sessions + 1
            for session in sorted(existing, key=lambda s: s.created_at)[:overflow]:
                RefreshTokenService.revoke_token_by_id(
                    db, session.id, reason="max_sessions_enforced"
                )

        from services.permissions.rbac_catalog_service import RbacCatalogService

        role = RbacCatalogService.apply_effective_role(db, user)
        user_data = {
            "username": user.username,
            "id": user.id,
            "role": role,
            "organization_id": user.organization_id,
            "email": user.email,
        }
        access_token = create_user_token(user_data)

        refresh_token, db_refresh_token = RefreshTokenService.create_refresh_token(
            db=db,
            user=user,
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if track_compliance_session:
            UserSessionService.create_for_refresh_token(
                db=db,
                user_id=user.id,
                refresh_token_row=db_refresh_token,
                access_token=access_token,
                user_agent=user_agent or device_info,
                ip_address=ip_address,
            )

        return access_token, refresh_token

    @staticmethod
    def get_current_user(db: Session, token: str) -> Optional[User]:
        """Get current user from JWT token"""
        from services.users import UserService
        from utils.jwt_config import verify_token

        payload = verify_token(token)
        if payload is None:
            return None

        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")

        if username is None or user_id is None:
            return None

        user = UserService.get_user_by_id(db, user_id)
        if user is not None:
            from services.permissions.rbac_catalog_service import RbacCatalogService

            RbacCatalogService.apply_effective_role(db, user)
        return user

    @staticmethod
    def register_user(
        db: Session,
        username: str,
        password: str,
        email: str,
        organization_id: int,
        phone_number: str = None,
    ) -> User:
        """Register a new user"""
        from services.users import UserService

        if UserService.check_username_exists(db, username):
            raise ValueError("Username already exists")

        if UserService.check_email_exists(db, email):
            raise ValueError("Email already exists")

        return UserService.create_user(
            db, username, password, email, organization_id, phone_number
        )

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using the project's hashing strategy"""
        from utils.jwt_config import get_password_hash

        return get_password_hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password using the project's hashing strategy"""
        from utils.jwt_config import verify_password as verify_password_hash

        return verify_password_hash(plain_password, hashed_password)

    @staticmethod
    def refresh_access_token(
        db: Session,
        refresh_token: str,
        device_info: str = None,
        ip_address: str = None,
        user_agent: str = None,
    ) -> Tuple[str, str]:
        """Refresh access token using refresh token"""
        user = RefreshTokenService.verify_refresh_token(db, refresh_token)
        if not user:
            raise ValueError("Invalid or expired refresh token")

        user_data = {
            "username": user.username,
            "id": user.id,
            "role": user.role,
            "organization_id": user.organization_id,
            "email": user.email,
        }
        access_token = create_user_token(user_data)

        new_refresh_token, _db_refresh_token = RefreshTokenService.rotate_token(
            db,
            refresh_token,
            user,
            device_info,
            ip_address,
            user_agent,
            access_token=access_token,
        )

        return access_token, new_refresh_token
