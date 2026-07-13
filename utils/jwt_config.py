from utils.datetime_utc import utc_now
import hashlib
import re
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from jwt.exceptions import PyJWTError

from config.settings import settings

# Get JWT configuration from centralized settings
SECRET_KEY = settings.jwt.secret_key
ALGORITHM = settings.jwt.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.jwt.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = settings.jwt.refresh_token_expire_days

# Legacy dev/seed passwords used SHA-256 hex (64 chars) before bcrypt migration.
_LEGACY_SHA256_HEX = re.compile(r"^[a-f0-9]{64}$")


def is_legacy_sha256_hash(hashed_password: str) -> bool:
    return bool(_LEGACY_SHA256_HEX.match(hashed_password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against bcrypt or (optionally) legacy SHA-256 hex hashes."""
    if is_legacy_sha256_hash(hashed_password):
        if not settings.password_policy.allow_legacy_sha256_hashes:
            return False
        return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        return False


def get_password_hash(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def needs_password_rehash(hashed_password: str) -> bool:
    """True when the stored hash should be upgraded to bcrypt."""
    return is_legacy_sha256_hash(hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token with role and organization info"""
    to_encode = data.copy()
    if expires_delta:
        expire = utc_now() + expires_delta
    else:
        expire = utc_now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    # PyJWT may return bytes on older versions; normalize to str.
    if isinstance(encoded_jwt, bytes):
        return encoded_jwt.decode("utf-8")
    return encoded_jwt


def create_user_token(user_data: dict) -> str:
    """Create a JWT token for a user with all necessary claims"""
    token_data = {
        "sub": user_data["username"],
        "user_id": user_data["id"],
        "role": user_data["role"],
        "organization_id": user_data["organization_id"],
        "email": user_data["email"],
    }
    return create_access_token(token_data)


def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except PyJWTError:
        return None


def hash_token(token: str) -> str:
    """Hash a token for secure storage"""
    return hashlib.sha256(token.encode()).hexdigest()
