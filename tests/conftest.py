from collections.abc import AsyncIterator, Mapping

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.health import HealthCheck
from app.core.config import Settings
from app.main import create_app
from tests.helpers import make_settings


async def _ok() -> None:
    return None


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def health_checks() -> Mapping[str, HealthCheck]:
    return {"database": _ok, "redis": _ok}


@pytest.fixture
def app(settings: Settings, health_checks: Mapping[str, HealthCheck]) -> FastAPI:
    return create_app(settings, health_checks=health_checks)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
