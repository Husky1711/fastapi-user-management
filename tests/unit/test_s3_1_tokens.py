"""Section 3.1: access tokens, opaque tokens and bounded password hashing (no database)."""

import asyncio
import threading
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
import pytest
from pydantic import SecretStr, ValidationError

from app.core import security
from app.core.config import AuthSettings, JwtSettings
from app.core.emails import InvalidEmail, normalize_email
from app.core.security import (
    AccessClaims,
    InvalidToken,
    decode_access_token,
    hash_token,
    issue_access_token,
    new_opaque_token,
    start_password_hashing,
    stop_password_hashing,
    verify_dummy_password,
)
from tests.helpers import strict_settings

NOW = datetime(2030, 1, 2, 3, 4, 5, tzinfo=UTC)
# 64 bytes: long enough for every allowed HMAC algorithm (RFC 7518 §3.2).
SETTINGS = JwtSettings(
    secret_key=SecretStr("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+/")
)
USER, SESSION = uuid.uuid4(), uuid.uuid4()


def _token(settings: JwtSettings = SETTINGS, now: datetime = NOW) -> str:
    token, _ = issue_access_token(settings, user_id=USER, session_id=SESSION, now=now)
    return token


def _forge(**changes: object) -> str:
    """A token signed with the right key but with claims changed or removed (None)."""
    payload = jwt.decode(_token(), options={"verify_signature": False})
    for name, value in changes.items():
        if value is None:
            payload.pop(name)
        else:
            payload[name] = value
    return jwt.encode(payload, SETTINGS.secret_key.get_secret_value(), algorithm="HS256")


def test_s3_1_01_access_token_round_trips_its_claims() -> None:
    token, issued = issue_access_token(SETTINGS, user_id=USER, session_id=SESSION, now=NOW)
    claims = decode_access_token(SETTINGS, token, now=NOW)
    assert claims == issued
    assert (claims.user_id, claims.session_id) == (USER, SESSION)
    assert claims.expires_at == NOW + timedelta(seconds=SETTINGS.access_ttl_seconds)
    raw = jwt.decode(token, options={"verify_signature": False})
    assert set(raw) == set(security.REQUIRED_CLAIMS)
    assert (raw["iss"], raw["aud"], raw["typ"]) == (SETTINGS.issuer, SETTINGS.audience, "access")
    assert "role" not in raw  # permissions are read live, never trusted from the token


@pytest.mark.parametrize(
    "token",
    [
        jwt.encode({"sub": "x"}, "another-key-of-thirty-two-bytes!", algorithm="HS256"),
        jwt.encode(
            jwt.decode(_token(), options={"verify_signature": False}), None, algorithm="none"
        ),
        jwt.encode(
            jwt.decode(_token(), options={"verify_signature": False}),
            SETTINGS.secret_key.get_secret_value(),
            algorithm="HS512",  # right key, but not the configured algorithm
        ),
    ],
)
def test_s3_1_02_wrong_key_none_or_other_algorithm_is_rejected(token: str) -> None:
    with pytest.raises(InvalidToken):
        decode_access_token(SETTINGS, token, now=NOW)


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "someone-else"},
        {"aud": "another-api"},
        {"typ": "refresh"},
        {"sub": None},
        {"sid": None},
        {"exp": None},
        {"jti": None},
        {"typ": None},
        {"sub": "not-a-uuid"},
    ],
)
def test_s3_1_03_wrong_or_missing_claims_are_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(InvalidToken):
        decode_access_token(SETTINGS, _forge(**changes), now=NOW)


def test_s3_1_04_expiry_and_issue_time_with_leeway() -> None:
    token = _token()
    ttl, leeway = SETTINGS.access_ttl_seconds, SETTINGS.leeway_seconds
    decode_access_token(SETTINGS, token, now=NOW + timedelta(seconds=ttl + leeway - 1))
    with pytest.raises(InvalidToken):
        decode_access_token(SETTINGS, token, now=NOW + timedelta(seconds=ttl + leeway))
    decode_access_token(SETTINGS, token, now=NOW - timedelta(seconds=leeway))
    with pytest.raises(InvalidToken):  # issued in the future, beyond the leeway
        decode_access_token(SETTINGS, token, now=NOW - timedelta(seconds=leeway + 1))


@pytest.mark.parametrize(
    "token", ["", "garbage", "a.b.c", _token()[:-5], "ünïcødé.tökén.x", " " + _token()]
)
def test_s3_1_05_malformed_tokens_raise_one_error_type(token: str) -> None:
    with pytest.raises(InvalidToken) as caught:
        decode_access_token(SETTINGS, token, now=NOW)
    assert caught.value.code == "auth.invalid_token"
    assert caught.value.status_code == 401
    assert caught.value.headers == {"WWW-Authenticate": 'Bearer error="invalid_token"'}


def test_s3_1_06_opaque_tokens_are_256_bit_and_hashed_with_sha256() -> None:
    token = new_opaque_token()
    assert len(token) >= 43  # 32 bytes in URL-safe base64
    assert set(token) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
    digest = hash_token(token)
    assert len(digest) == 32
    assert hash_token(token) == digest
    assert hash_token(token + "x") != digest


def test_s3_1_07_opaque_tokens_do_not_repeat() -> None:
    assert len({new_opaque_token() for _ in range(10_000)}) == 10_000


async def test_s3_1_08_at_most_the_configured_number_of_hashes_run_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running = peak = 0
    lock = threading.Lock()
    real_hash = security._hash

    def counting_hash(password: str) -> str:
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        try:
            return real_hash(password)
        finally:
            with lock:
                running -= 1

    monkeypatch.setattr(security, "_hash", counting_hash)
    start_password_hashing(4)
    try:
        hashes = await asyncio.gather(
            *(security.hash_password(f"pw-{i:02}-long-enough") for i in range(20))
        )
        assert peak <= 4
        assert peak >= 2  # they did run in parallel
        assert await security.verify_password(hashes[7], "pw-07-long-enough")
    finally:
        stop_password_hashing()


async def test_s3_1_09_restarting_the_pool_closes_the_old_one() -> None:
    start_password_hashing(2)
    old = security._executor
    start_password_hashing(3)
    assert old is not None
    with pytest.raises(RuntimeError):  # shut down: accepts no more work
        old.submit(print)
    assert security._executor is not old
    assert await security.verify_password(await security.hash_password("x" * 12), "x" * 12)
    stop_password_hashing()
    assert security._executor is None


async def test_s3_1_10_dummy_verify_does_real_argon2_work(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    real_verify = security._verify

    def spy(password_hash: str, password: str) -> bool:
        calls.append(password_hash)
        return real_verify(password_hash, password)

    monkeypatch.setattr(security, "_verify", spy)
    assert await verify_dummy_password("anything at all") is False
    assert await verify_dummy_password("anything at all") is False
    assert len(calls) == 2
    assert calls[0].startswith("$argon2id$v=19$m=65536,t=3,p=4$")  # same cost as a real hash


@pytest.mark.parametrize("email", ["grace@exämple.com", "grace@例え.jp", "gräce@example.com"])
def test_s3_1_11_internationalised_addresses_are_refused(email: str) -> None:
    with pytest.raises(InvalidEmail) as caught:
        normalize_email(email)
    assert caught.value.code == "user.email_invalid"


@pytest.mark.parametrize(
    ("section", "values"),
    [
        (JwtSettings, {"access_ttl_seconds": 59}),
        (JwtSettings, {"access_ttl_seconds": 3601}),
        (JwtSettings, {"issuer": ""}),
        (JwtSettings, {"audience": ""}),
        (JwtSettings, {"leeway_seconds": 61}),
        (AuthSettings, {"refresh_ttl": timedelta(minutes=4)}),
        (AuthSettings, {"refresh_ttl": timedelta(days=91), "session_max_age": timedelta(days=91)}),
        (AuthSettings, {"refresh_ttl": timedelta(days=30), "session_max_age": timedelta(days=14)}),
        (AuthSettings, {"session_max_age": timedelta(days=366)}),
        (AuthSettings, {"lockout_threshold": 2}),
        (AuthSettings, {"password_hash_workers": 0}),
        (AuthSettings, {"session_strategy": "forever"}),
    ],
)
def test_s3_1_12_unsafe_token_and_auth_settings_are_refused(
    section: type[JwtSettings] | type[AuthSettings], values: dict[str, object]
) -> None:
    with pytest.raises(ValidationError):
        section.model_validate(values)


def test_s3_1_13_decoding_twice_gives_the_same_claims() -> None:
    token = _token()
    first = decode_access_token(SETTINGS, token, now=NOW)
    assert decode_access_token(SETTINGS, token, now=NOW) == first
    assert isinstance(first, AccessClaims)


@pytest.mark.parametrize(
    ("algorithm", "length", "safe"),
    [
        ("HS256", 32, True),
        ("HS384", 47, False),
        ("HS384", 48, True),
        ("HS512", 63, False),
        ("HS512", 64, True),
    ],
)
def test_s3_1_12_secret_must_be_as_long_as_the_hmac_output(
    algorithm: Literal["HS256", "HS384", "HS512"], length: int, safe: bool
) -> None:
    secret = ("0123456789abcdefghijklmnopqrstuvwxyz" * 2)[:length]
    settings = strict_settings(jwt=JwtSettings(secret_key=SecretStr(secret), algorithm=algorithm))
    problems = [p for p in settings.safety_problems() if "JWT__SECRET_KEY" in p]
    assert (problems == []) is safe


def test_s3_1_12_session_limits_accept_asvs_level_2_durations() -> None:
    """ISO 8601 durations, down to ASVS level 2: 30 minutes idle, 12 hours absolute."""
    policy = AuthSettings.model_validate({"refresh_ttl": "PT30M", "session_max_age": "PT12H"})
    assert (policy.refresh_ttl, policy.session_max_age) == (
        timedelta(minutes=30),
        timedelta(hours=12),
    )
    assert AuthSettings(refresh_ttl=timedelta(minutes=5)).refresh_ttl == timedelta(minutes=5)
