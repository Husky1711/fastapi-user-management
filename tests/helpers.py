"""Shared test helpers (plain functions; fixtures live in conftest.py)."""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from starlette.types import Message

from app.core.config import DatabaseSettings, Environment, JwtSettings, RedisSettings, Settings
from app.main import create_app
from app.services.health import HealthCheck

SAFE_SECRET = "N9xq2Lr7VbKp4Zt8Ws1Ye6Hd3Gu0Mf5JcQaRtYsBnEi"  # varied, ≥ 32 chars (test only)
ALLOWED_ORIGIN = "https://app.example.com"
CRASH_PATH = "/_test/crash"
CRASH_SECRET = "hunter2"
SAFE_DB = DatabaseSettings(url="postgresql+asyncpg://app:s3cret@db:5432/app")
SAFE_REDIS = RedisSettings(url="redis://:r3dis-pass@cache:6379/0")


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
        "redis": SAFE_REDIS,
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
    """App without starting its lifespan. With no `checks`, readiness reports not ready."""
    return create_app(settings or make_settings(), health_checks=checks)


def add_crash_route(app: FastAPI) -> FastAPI:
    """Test-only route whose unhandled error message contains a 'secret'."""

    @app.get(CRASH_PATH)
    async def crash() -> None:
        raise RuntimeError(f"database password is {CRASH_SECRET}")

    return app


STREAM_PATH = "/_test/stream"


def add_broken_stream_route(app: FastAPI) -> FastAPI:
    """Test-only route that fails after its streamed response has started."""

    async def broken_stream() -> AsyncIterator[bytes]:
        yield b"partial"
        raise RuntimeError("stream broke")

    @app.get(STREAM_PATH)
    async def stream() -> StreamingResponse:
        return StreamingResponse(broken_stream())

    return app


async def receive_disconnect() -> Message:
    return {"type": "http.disconnect"}


class RecordingSend:
    """ASGI `send` that records every message."""

    def __init__(self) -> None:
        self.messages: list[Message] = []

    async def __call__(self, message: Message) -> None:
        self.messages.append(message)


def http_scope(method: str = "GET", path: str = "/") -> dict[str, object]:
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [],
        "client": ("10.0.0.1", 50000),
        "server": ("test", 80),
    }


@asynccontextmanager
async def client_for(
    app: FastAPI, *, raise_app_exceptions: bool = True
) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
