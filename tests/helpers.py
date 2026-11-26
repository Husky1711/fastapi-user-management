"""Shared test helpers (plain functions; fixtures live in conftest.py)."""

from typing import Any

from app.core.config import DatabaseSettings, Environment, Settings

SAFE_SECRET = "a" * 48
SAFE_DB = DatabaseSettings(url="postgresql+asyncpg://app:s3cret@db:5432/app")


def make_settings(**overrides: Any) -> Settings:
    """Settings for tests: ignores any local .env; override only what a test cares about."""
    values: dict[str, Any] = {"environment": Environment.TEST}
    values.update(overrides)
    return Settings(_env_file=None, **values)
