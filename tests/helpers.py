"""Shared test helpers (plain functions; fixtures live in conftest.py)."""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.core.config import DatabaseSettings, Environment, JwtSettings, Settings
from app.main import create_app
from app.services.health import HealthCheck

SAFE_SECRET = "a" * 48
SAFE_DB = DatabaseSettings(url="postgresql+asyncpg://app:s3cret@db:5432/app")


# Any: values are forwarded unchanged to Settings' own typed constructor, which validates them.
def make_settings(**overrides: Any) -> Settings:
    """Settings for tests: ignores any local .env; override only what a test cares about."""
    values: dict[str, Any] = {"environment": Environment.TEST}
    values.update(overrides)
    return Settings(_env_file=None, **values)


# Any: forwarded to make_settings (see above).
def strict_settings(
    environment: Environment = Environment.PRODUCTION, **overrides: Any
) -> Settings:
    """Settings that pass the staging/production safety checks, plus any overrides."""
    values: dict[str, Any] = {
        "environment": environment,
        "jwt": JwtSettings(secret_key=SecretStr(SAFE_SECRET)),
        "database": SAFE_DB,
    }
    values.update(overrides)
    return make_settings(**values)


async def check_ok() -> None:
    return None


async def check_never_finishes() -> None:
    """A dependency that hangs forever (waits on an event nobody sets; no sleeping)."""
    await asyncio.Event().wait()


def app_with(
    settings: Settings | None = None, checks: Mapping[str, HealthCheck] | None = None
) -> FastAPI:
    return create_app(settings or make_settings(), health_checks=checks if checks else {})


@asynccontextmanager
async def client_for(
    app: FastAPI, *, raise_app_exceptions: bool = True
) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
