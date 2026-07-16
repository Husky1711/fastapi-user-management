"""H5 — soft-delete must kill login, refresh, and API keys atomically."""

from __future__ import annotations

import uuid

import pytest

from models.user_model import ApiKey, RefreshToken, User
from services.auth.auth_service import AuthService
from services.auth.refresh_token_service import RefreshTokenService
from services.permissions.api_key_service import ApiKeyService
from services.users.user_service import UserService
from utils.database import SessionLocal
from utils.jwt_config import get_password_hash

pytestmark = pytest.mark.integration


def _suffix() -> str:
    return uuid.uuid4().hex[:10]


@pytest.mark.integration
def test_soft_delete_kills_login_refresh_and_api_key():
    db = SessionLocal()
    suffix = _suffix()
    username = f"h5kill-{suffix}"
    email = f"h5kill-{suffix}@example.com"
    password = "TempPass123!"
    raw_refresh: str | None = None
    raw_api_key: str | None = None
    target_id: int | None = None

    try:
        editor = db.query(User).filter_by(username="test_super_admin").one()
        target = User(
            username=username,
            email=email,
            password_hash=get_password_hash(password),
            status="active",
            role="user",
            organization_id=1,
            phone_number="1234567890",
        )
        db.add(target)
        db.commit()
        db.refresh(target)
        target_id = target.id

        from services.permissions.rbac_catalog_service import RbacCatalogService

        RbacCatalogService.sync_user_system_role(db, target.id, "user", commit=True)

        access_token, raw_refresh = AuthService.create_tokens_for_user(
            db, target, device_info="h5-test"
        )
        assert access_token
        assert raw_refresh

        key_result = ApiKeyService.create_api_key(
            db=db,
            user_id=target.id,
            organization_id=1,
            key_name=f"h5-key-{suffix}",
            created_by=editor.id,
            permissions=["read:users"],
        )
        assert key_result.get("success") is True, key_result
        raw_api_key = key_result.get("key_value")
        assert raw_api_key, key_result

        # Soft-delete as admin
        result = UserService.soft_delete_user(db, editor, target.id)
        assert result["success"] is True, result

        # Login fails
        assert UserService.authenticate_user(db, username, password) is None

        # Refresh fails (token revoked + deleted-user guard)
        assert RefreshTokenService.verify_refresh_token(db, raw_refresh) is None

        # API key fails
        validation = ApiKeyService.validate_api_key(db, raw_api_key)
        assert validation.get("success") is False

        # Bearer resolve fails
        assert AuthService.get_current_user(db, access_token) is None

        # Credentials rows are cleaned
        active_refresh = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.user_id == target_id,
                RefreshToken.is_revoked == False,
            )
            .count()
        )
        assert active_refresh == 0
        active_keys = (
            db.query(ApiKey)
            .filter(ApiKey.user_id == target_id, ApiKey.is_active == True)
            .count()
        )
        assert active_keys == 0

        # Presenting the revoked refresh again still fails (no resurrection)
        assert RefreshTokenService.verify_refresh_token(db, raw_refresh) is None
    finally:
        if target_id is not None:
            db.query(ApiKey).filter(ApiKey.user_id == target_id).delete(
                synchronize_session=False
            )
            db.query(RefreshToken).filter(RefreshToken.user_id == target_id).delete(
                synchronize_session=False
            )
            db.query(User).filter(User.id == target_id).delete(synchronize_session=False)
            db.commit()
        db.close()
