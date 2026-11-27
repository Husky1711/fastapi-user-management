"""Passwords (Argon2id), access tokens (JWT) and opaque tokens (refresh, reset, invite).

Argon2id is deliberately slow and memory-hard (~tens of ms, 64 MiB per hash). It runs on a
dedicated, bounded thread pool, so it never blocks the event loop and a burst of logins can
use at most `workers x 64 MiB` (ADR-0006, step 2 review R1-08).
"""

import asyncio
import hashlib
import secrets
import unicodedata
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta

import jwt
from argon2 import PasswordHasher, profiles
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import JwtSettings
from app.core.errors import Unauthorized, Unprocessable

# RFC 9106 "second recommended" profile: Argon2id, t=3, m=64 MiB, p=4.
_hasher = PasswordHasher.from_parameters(profiles.RFC_9106_LOW_MEMORY)

PASSWORD_MIN_LENGTH = 12  # NIST SP 800-63B allows 8; 12 is the common modern floor
PASSWORD_MAX_LENGTH = 128  # bounds hashing cost per request
DEFAULT_HASH_WORKERS = 4
OPAQUE_TOKEN_BYTES = 32  # 256 bits
ACCESS_TOKEN_TYPE = "access"  # noqa: S105 - a token type name, not a secret
REQUIRED_CLAIMS = ("sub", "sid", "iat", "exp", "iss", "aud", "jti", "typ")


class WeakPassword(Unprocessable):
    """The password breaks a password rule. The message is safe to show to the user."""

    default_code = "user.password_weak"
    default_detail = "Choose a stronger password."


class InvalidToken(Unauthorized):
    """Any problem with a presented token. One code and message for every cause, so a client
    can't probe which check failed."""

    default_code = "auth.invalid_token"
    default_detail = "The token is invalid or has expired."

    def __init__(self) -> None:
        super().__init__(headers={"WWW-Authenticate": 'Bearer error="invalid_token"'})


def _normalize(password: str) -> str:
    # NFKC: the same password typed on different keyboards (composed / decomposed) matches.
    return unicodedata.normalize("NFKC", password)


def check_password_rules(password: str) -> None:
    normalized = _normalize(password)
    if len(normalized) < PASSWORD_MIN_LENGTH:
        msg = f"Password must be at least {PASSWORD_MIN_LENGTH} characters."
        raise WeakPassword(msg)
    if len(normalized) > PASSWORD_MAX_LENGTH:
        msg = f"Password must be at most {PASSWORD_MAX_LENGTH} characters."
        raise WeakPassword(msg)
    if not normalized.strip():
        msg = "Password must not be only spaces."
        raise WeakPassword(msg)
    if any(unicodedata.category(char) == "Cc" for char in normalized):
        # NUL, escape, newline...: never typed on purpose, and they break forms and terminals.
        msg = "Password must not contain control characters."
        raise WeakPassword(msg)


_executor: ThreadPoolExecutor | None = None


def start_password_hashing(workers: int = DEFAULT_HASH_WORKERS) -> None:
    """(Re)create the hashing pool. Called by the app lifespan and the CLI."""
    global _executor
    stop_password_hashing()
    _executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="argon2")


def stop_password_hashing() -> None:
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=True)
        _executor = None


def _pool() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:  # e.g. a script that never called start_password_hashing()
        _executor = ThreadPoolExecutor(DEFAULT_HASH_WORKERS, thread_name_prefix="argon2")
    return _executor


def _hash(password: str) -> str:
    return _hasher.hash(_normalize(password))


def _verify(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, _normalize(password))
    except (VerificationError, InvalidHashError):  # mismatch, corrupt or unknown hash
        return False


async def hash_password(password: str) -> str:
    return await asyncio.get_running_loop().run_in_executor(_pool(), _hash, password)


async def verify_password(password_hash: str, password: str) -> bool:
    return await asyncio.get_running_loop().run_in_executor(
        _pool(), _verify, password_hash, password
    )


_dummy_hash: str | None = None


async def verify_dummy_password(password: str) -> bool:
    """Spend exactly the work of a real verify, for a user that doesn't exist, so response
    time doesn't reveal which emails are registered. Always False."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = await hash_password(secrets.token_urlsafe(16))
    await verify_password(_dummy_hash, password)
    return False


def password_needs_rehash(password_hash: str) -> bool:
    """True when the hash uses older parameters than today's (rehash after a good login)."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def new_opaque_token() -> str:
    """256 random bits, URL-safe. Give it to the client; store only `hash_token(token)`."""
    return secrets.token_urlsafe(OPAQUE_TOKEN_BYTES)


def hash_token(token: str) -> bytes:
    """SHA-256 digest (32 bytes). Enough for random 256-bit tokens: no salt or slow hash is
    needed when the input can't be guessed."""
    return hashlib.sha256(token.encode()).digest()


@dataclass(frozen=True, slots=True)
class AccessClaims:
    user_id: uuid.UUID
    session_id: uuid.UUID  # the session family, so revocation takes effect at once
    token_id: str
    expires_at: datetime


def issue_access_token(
    settings: JwtSettings, *, user_id: uuid.UUID, session_id: uuid.UUID, now: datetime
) -> tuple[str, AccessClaims]:
    expires_at = now + timedelta(seconds=settings.access_ttl_seconds)
    claims = AccessClaims(user_id, session_id, secrets.token_urlsafe(16), expires_at)
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": settings.issuer,
        "aud": settings.audience,
        "jti": claims.token_id,
        "typ": ACCESS_TOKEN_TYPE,
    }
    secret = settings.secret_key.get_secret_value()
    return jwt.encode(payload, secret, algorithm=settings.algorithm), claims


def decode_access_token(settings: JwtSettings, token: str, *, now: datetime) -> AccessClaims:
    """Verify signature, algorithm, issuer, audience, type, expiry and issue time.

    Raises `InvalidToken` for every failure; the cause is never shown to the client.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],  # exactly one: no "none", no algorithm switching
            audience=settings.audience,
            issuer=settings.issuer,
            leeway=settings.leeway_seconds,
            options={"require": list(REQUIRED_CLAIMS), "verify_exp": False, "verify_iat": False},
        )
        return _checked_claims(payload, settings, now)
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as error:
        raise InvalidToken from error


def _checked_claims(
    payload: dict[str, object], settings: JwtSettings, now: datetime
) -> AccessClaims:
    # Time is checked against the app clock (injectable), not PyJWT's own `time.time()`.
    leeway = settings.leeway_seconds
    expires = int(str(payload["exp"]))
    issued = int(str(payload["iat"]))
    instant = now.timestamp()
    if (
        payload["typ"] != ACCESS_TOKEN_TYPE
        or expires <= instant - leeway
        or issued > instant + leeway
    ):
        raise ValueError("token type or time window")
    return AccessClaims(
        user_id=uuid.UUID(str(payload["sub"])),
        session_id=uuid.UUID(str(payload["sid"])),
        token_id=str(payload["jti"]),
        expires_at=datetime.fromtimestamp(expires, tz=now.tzinfo),
    )
