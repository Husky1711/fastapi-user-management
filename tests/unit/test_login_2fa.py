"""Unit tests for field encryption and 2FA login challenge."""

import pyotp
import pytest
from fastapi.testclient import TestClient

from services.auth.login_2fa_service import Login2FAService
from services.auth.two_factor_secret_service import TwoFactorSecretService
from utils.field_encryption import decrypt_value, encrypt_value


def test_field_encryption_roundtrip() -> None:
    plaintext = "JBSWY3DPEHPK3PXP"
    encrypted = encrypt_value(plaintext)
    assert encrypted.startswith("enc:")
    assert decrypt_value(encrypted) == plaintext


def test_field_encryption_legacy_plaintext() -> None:
    assert decrypt_value("JBSWY3DPEHPK3PXP") == "JBSWY3DPEHPK3PXP"


@pytest.mark.integration
@pytest.mark.auth
def test_login_requires_2fa_before_tokens(test_client_manager) -> None:
    from models.user_model import User
    from tests.utils.test_helpers import _get_app

    db = test_client_manager.get_db_session()
    user = db.query(User).filter(User.username == "testuser").first()
    assert user is not None

    secret = pyotp.random_base32()
    previous_enabled = user.is_2fa_enabled
    previous_secret = user.two_factor_secret
    previous_codes = user.backup_codes
    try:
        user.two_factor_secret = TwoFactorSecretService.store_secret(secret)
        user.is_2fa_enabled = True
        db.commit()

        client = TestClient(_get_app())
        login = client.post(
            "/api/v1/login",
            json={"username": "testuser", "password": "user123"},
        )
        assert login.status_code == 200
        body = login.json()
        assert body.get("requires_2fa") is True
        assert body.get("challenge_token")
        assert "access_token" not in body

        totp = pyotp.TOTP(secret).now()
        # Invalid code must not issue tokens and must keep challenge usable
        denied = client.post(
            "/api/v1/login/2fa",
            json={
                "challenge_token": body["challenge_token"],
                "totp_code": "000000",
            },
        )
        assert denied.status_code in (400, 401, 403)
        assert "access_token" not in (denied.json() if denied.content else {})

        totp = pyotp.TOTP(secret).now()
        complete = client.post(
            "/api/v1/login/2fa",
            json={
                "challenge_token": body["challenge_token"],
                "totp_code": totp,
            },
        )
        assert complete.status_code == 200
        assert complete.json().get("access_token")
    finally:
        user.is_2fa_enabled = previous_enabled
        user.two_factor_secret = previous_secret
        user.backup_codes = previous_codes
        db.commit()


@pytest.mark.integration
@pytest.mark.auth
def test_login_2fa_rejects_stale_challenge(test_client_manager) -> None:
    from models.user_model import User
    from tests.utils.test_helpers import _get_app
    from utils.redis_config import RedisClient

    # Avoid cross-test IP bucket exhaustion on /login/2fa
    try:
        client = RedisClient.get_client()
        for key in list(client.scan_iter(match="rate_limit:login:*")):
            client.delete(key)
    except Exception:
        pass

    db = test_client_manager.get_db_session()
    user = db.query(User).filter(User.username == "testuser").first()
    assert user is not None

    secret = pyotp.random_base32()
    previous_enabled = user.is_2fa_enabled
    previous_secret = user.two_factor_secret
    try:
        user.two_factor_secret = TwoFactorSecretService.store_secret(secret)
        user.is_2fa_enabled = True
        db.commit()

        http = TestClient(_get_app())
        login = http.post(
            "/api/v1/login",
            json={"username": "testuser", "password": "user123"},
        )
        assert login.status_code == 200
        assert login.json().get("requires_2fa") is True

        stale = http.post(
            "/api/v1/login/2fa",
            json={
                "challenge_token": "not-a-real-challenge-token-xx",
                "totp_code": "123456",
            },
        )
        assert stale.status_code == 401
        assert "access_token" not in stale.json()
    finally:
        user.is_2fa_enabled = previous_enabled
        user.two_factor_secret = previous_secret
        db.commit()
