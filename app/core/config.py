"""Application settings.

One `Settings` object, loaded from environment variables (and `.env` in development).
Nested sections use a double underscore: `DATABASE__URL`, `JWT__SECRET_KEY`, ...

Get settings through `get_settings()`; never read `os.environ` directly. Settings, including
every nested section, are immutable once loaded, so they can't be changed after the startup
safety check has passed.
"""

from enum import StrEnum
from functools import lru_cache
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "insecure-development-secret-change-me-before-production"  # noqa: S105
MIN_JWT_SECRET_LENGTH = 32
MIN_JWT_SECRET_DISTINCT_CHARS = 10  # rejects "aaaa…" or "abababab…" style secrets
DEV_REDIS_PASSWORD = "redis-dev-password"  # noqa: S105 - published in .env.example and Compose
# Passwords published in this repository or used as image defaults. Never allowed in strict
# environments.
WELL_KNOWN_PASSWORDS = frozenset({"postgres", DEV_REDIS_PASSWORD, "password", "changeme"})


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


# Staging is usually internet-facing and often holds copies of real data, so it gets the same
# safety checks as production.
STRICT_ENVIRONMENTS = frozenset({Environment.STAGING, Environment.PRODUCTION})
DOCS_ENVIRONMENTS = frozenset({Environment.DEVELOPMENT, Environment.TEST})


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class _Section(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DatabaseSettings(_Section):
    # SecretStr: the URL carries the password, so it must not appear in repr, dumps or logs.
    # Unwrapped only in app/infra/.
    url: SecretStr = SecretStr("postgresql+asyncpg://postgres:postgres@localhost:5432/usermgmt")
    pool_size: int = Field(default=5, ge=1, le=100)
    max_overflow: int = Field(default=5, ge=0, le=100)
    pool_timeout_seconds: float = Field(default=10.0, gt=0)
    # Fail fast when the host doesn't answer (asyncpg's own default is 60 s).
    connect_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    echo: bool = False


class RedisSettings(_Section):
    url: SecretStr = SecretStr(f"redis://:{DEV_REDIS_PASSWORD}@localhost:6379/0")


class JwtSettings(_Section):
    secret_key: SecretStr = SecretStr(DEFAULT_JWT_SECRET)
    # HMAC only: an asymmetric algorithm would need a key pair, and "none" must never be possible.
    algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    issuer: str = Field(default="user-management-api", min_length=1, max_length=200)
    audience: str = Field(default="user-management-clients", min_length=1, max_length=200)
    # Short-lived: revocation is also checked per request (session lookup), but a short TTL
    # limits what a leaked token can do if that check is ever bypassed.
    access_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    # Clock difference tolerated between servers when checking `exp` / `iat`.
    leeway_seconds: int = Field(default=10, ge=0, le=60)


class SessionStrategy(StrEnum):
    ALLOW_MULTIPLE = "allow_multiple"  # every login adds a session
    REPLACE_ALL = "replace_all"  # a login ends every other session
    LIMIT_SESSIONS = "limit_sessions"  # at most `max_sessions`; the oldest is ended
    REPLACE_SAME_DEVICE = "replace_same_device"  # a login ends sessions with the same user agent


class AuthSettings(_Section):
    signup_enabled: bool = True
    refresh_ttl_days: int = Field(default=14, ge=1, le=90)
    # A session can be refreshed for at most this long after its first login.
    session_max_age_days: int = Field(default=30, ge=1, le=365)
    lockout_threshold: int = Field(default=5, ge=3, le=20)
    lockout_minutes: int = Field(default=15, ge=1, le=1440)
    session_strategy: SessionStrategy = SessionStrategy.ALLOW_MULTIPLE
    max_sessions: int = Field(default=5, ge=1, le=100)
    # Argon2id uses 64 MiB per hash: at most this many run at once (memory = workers x 64 MiB).
    password_hash_workers: int = Field(default=4, ge=1, le=32)

    @model_validator(mode="after")
    def _max_age_covers_refresh_ttl(self) -> Self:
        if self.session_max_age_days < self.refresh_ttl_days:
            raise ValueError("AUTH__SESSION_MAX_AGE_DAYS must be at least AUTH__REFRESH_TTL_DAYS")
        return self


class CorsSettings(_Section):
    allow_origins: tuple[str, ...] = ()
    allow_credentials: bool = True

    @model_validator(mode="after")
    def _reject_wildcard_with_credentials(self) -> Self:
        # Browsers forbid this combination, and Starlette would "fix" it by reflecting any
        # origin, which lets every website make credentialed requests. Never allow it.
        if "*" in self.allow_origins and self.allow_credentials:
            raise ValueError("CORS allow_origins '*' cannot be combined with allow_credentials")
        return self


class LogSettings(_Section):
    level: LogLevel = LogLevel.INFO
    # Records waiting to be written. When full (stdout stuck), new records are dropped and
    # counted instead of using unbounded memory.
    queue_size: int = Field(default=10_000, ge=100, le=1_000_000)


class HealthSettings(_Section):
    check_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    # Readiness results are reused for this long, so a flood of probes costs at most one
    # database and one Redis round trip per window. 0 disables the cache.
    cache_seconds: float = Field(default=1.0, ge=0, le=30)


class UnsafeConfigurationError(RuntimeError):
    """Raised at startup when settings are unsafe for a staging or production environment."""

    def __init__(self, environment: Environment, problems: list[str]) -> None:
        self.problems = problems
        super().__init__(f"Unsafe configuration for {environment}: " + "; ".join(problems))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        frozen=True,
    )

    app_name: str = "User Management API"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    jwt: JwtSettings = Field(default_factory=JwtSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    cors: CorsSettings = Field(default_factory=CorsSettings)
    log: LogSettings = Field(default_factory=LogSettings)
    health: HealthSettings = Field(default_factory=HealthSettings)

    @property
    def is_strict(self) -> bool:
        """Staging and production: unsafe settings stop the app from starting."""
        return self.environment in STRICT_ENVIRONMENTS

    @property
    def docs_enabled(self) -> bool:
        """Interactive API docs are served only in development and test."""
        return self.environment in DOCS_ENVIRONMENTS

    def safety_problems(self) -> list[str]:
        """Every reason these settings are unsafe for a strict environment (empty if safe)."""
        if not self.is_strict:
            return []
        problems = _jwt_secret_problems(self.jwt.secret_key.get_secret_value())
        if self.debug:
            problems.append("DEBUG must be false")
        problems += _url_password_problems("DATABASE__URL", self.database.url)
        problems += _url_password_problems("REDIS__URL", self.redis.url)
        return problems

    def ensure_safe(self) -> None:
        problems = self.safety_problems()
        if problems:
            raise UnsafeConfigurationError(self.environment, problems)


def _jwt_secret_problems(secret: str) -> list[str]:
    if secret == DEFAULT_JWT_SECRET:
        return ["JWT__SECRET_KEY is the development default"]
    if len(secret) < MIN_JWT_SECRET_LENGTH:
        return [f"JWT__SECRET_KEY must be at least {MIN_JWT_SECRET_LENGTH} characters"]
    if len(set(secret)) < MIN_JWT_SECRET_DISTINCT_CHARS:
        return ["JWT__SECRET_KEY is too repetitive; generate a random one"]
    return []


def _url_password_problems(name: str, url: SecretStr) -> list[str]:
    try:
        password = urlsplit(url.get_secret_value()).password
    except ValueError:  # malformed URL: we can't prove it carries a real password
        password = None
    if not password:
        return [f"{name} must include a password"]
    if password in WELL_KNOWN_PASSWORDS:
        return [f"{name} uses a well-known default password"]
    return []


@lru_cache
def get_settings() -> Settings:
    """Settings for the running process, loaded once."""
    return Settings()
