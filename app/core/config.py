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

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "insecure-development-secret-change-me-before-production"  # noqa: S105
MIN_JWT_SECRET_LENGTH = 32
DEFAULT_DATABASE_CREDENTIALS = "postgres:postgres@"


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
    url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/usermgmt"
    pool_size: int = Field(default=5, ge=1, le=100)
    max_overflow: int = Field(default=5, ge=0, le=100)
    pool_timeout_seconds: float = Field(default=10.0, gt=0)
    echo: bool = False


class RedisSettings(_Section):
    url: str = "redis://localhost:6379/0"


class JwtSettings(_Section):
    secret_key: SecretStr = SecretStr(DEFAULT_JWT_SECRET)
    # HMAC only: an asymmetric algorithm would need a key pair, and "none" must never be possible.
    algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"


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
        problems: list[str] = []
        secret = self.jwt.secret_key.get_secret_value()
        if secret == DEFAULT_JWT_SECRET:
            problems.append("JWT__SECRET_KEY is the development default")
        elif len(secret) < MIN_JWT_SECRET_LENGTH:
            problems.append(f"JWT__SECRET_KEY must be at least {MIN_JWT_SECRET_LENGTH} characters")
        if self.debug:
            problems.append("DEBUG must be false")
        if DEFAULT_DATABASE_CREDENTIALS in self.database.url:
            problems.append("DATABASE__URL uses the default postgres:postgres credentials")
        return problems

    def ensure_safe(self) -> None:
        problems = self.safety_problems()
        if problems:
            raise UnsafeConfigurationError(self.environment, problems)


@lru_cache
def get_settings() -> Settings:
    """Settings for the running process, loaded once."""
    return Settings()
