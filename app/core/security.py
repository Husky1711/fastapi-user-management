"""Password hashing (Argon2id) and password rules.

Hashing is deliberately slow (~tens of ms, 64 MiB), so it runs in a worker thread and never
blocks the event loop. JWT and token hashing arrive in roadmap step 3.
"""

import asyncio
import unicodedata

from argon2 import PasswordHasher, profiles
from argon2.exceptions import InvalidHashError, VerificationError

# RFC 9106 "second recommended" profile: Argon2id, t=3, m=64 MiB, p=4.
_hasher = PasswordHasher.from_parameters(profiles.RFC_9106_LOW_MEMORY)

PASSWORD_MIN_LENGTH = 12  # NIST SP 800-63B allows 8; 12 is the common modern floor
PASSWORD_MAX_LENGTH = 128  # bounds hashing cost per request


class WeakPassword(ValueError):
    """The password breaks a password rule. The message is safe to show to the user."""


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


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hasher.hash, _normalize(password))


def _verify(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, _normalize(password))
    except (VerificationError, InvalidHashError):  # mismatch, corrupt or unknown hash
        return False


async def verify_password(password_hash: str, password: str) -> bool:
    return await asyncio.to_thread(_verify, password_hash, password)


def password_needs_rehash(password_hash: str) -> bool:
    """True when the hash uses older parameters than today's (rehash after a good login)."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True
