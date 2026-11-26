"""Application settings.

One `Settings` object, loaded from environment variables (and `.env` in development).
Nested sections use a double underscore: `DATABASE__URL`, `JWT__SECRET_KEY`, ...

Get settings through `get_settings()`; never read `os.environ` directly.
"""

from enum import StrEnum
from functools import lru_cache
from typing import Self

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "insecure-development-secret-change-me-before-production"  # noqa: S105
MIN_JWT_SECRET_LENGTH = 32
DEFAULT_DATABASE_CREDENTIALS = "postgres:postgres@"


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class DatabaseSettings(BaseModel):
    url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/usermgmt"
    pool_size: int = Field(default=5, ge=1, le=100)
    max_overflow: int = Field(default=5, ge=0, le=100)
    pool_timeout_seconds: float = Field(default=10.0, gt=0)
    echo: bool = False


class RedisSettings(BaseModel):
    url: str = "redis://localhost:6379/0"


class JwtSettings(BaseModel):
    secret_key: SecretStr = SecretStr(DEFAULT_JWT_SECRET)
    algorithm: str = "HS256"


class CorsSettings(BaseModel):
    allow_origins: list[str] = Field(default_factory=list)
    allow_credentials: bool = True

    @model_validator(mode="after")
    def _reject_wildcard_with_credentials(self) -> Self:
        # Browsers forbid this combination, and Starlette would "fix" it by reflecting any
        # origin, which lets every website make credentialed requests. Never allow it.
        if "*" in self.allow_origins and self.allow_credentials:
            raise ValueError("CORS allow_origins '*' cannot be combined with allow_credentials")
        return self


class LogSettings(BaseModel):
    level: LogLevel = LogLevel.INFO


class HealthSettings(BaseModel):
    check_timeout_seconds: float = Field(default=2.0, gt=0, le=30)


class UnsafeConfigurationError(RuntimeError):
    """Raised at startup when production settings are unsafe."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("Unsafe production configuration: " + "; ".join(problems))


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
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    @property
    def docs_enabled(self) -> bool:
        """Interactive API docs are served everywhere except production."""
        return not self.is_production

    def production_problems(self) -> list[str]:
        """Return every reason these settings are unsafe for production (empty if safe)."""
        if not self.is_production:
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

    def ensure_safe_for_production(self) -> None:
        problems = self.production_problems()
        if problems:
            raise UnsafeConfigurationError(problems)


@lru_cache
def get_settings() -> Settings:
    """Settings for the running process, loaded once."""
    return Settings()
