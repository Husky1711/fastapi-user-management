import asyncio
import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import DatabaseSettings, HealthSettings, RedisSettings
from app.main import create_app
from tests.helpers import make_settings


async def _ok() -> None:
    return None


async def _fail() -> None:
    raise ConnectionError("postgresql://user:secret@db/app refused")


async def _hang() -> None:
    await asyncio.sleep(10)


async def test_liveness(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


async def test_readiness_when_all_checks_pass(client: AsyncClient) -> None:
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}


async def test_readiness_fails_without_leaking_error_details() -> None:
    app = create_app(make_settings(), health_checks={"database": _fail, "redis": _ok})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "error", "redis": "ok"},
    }
    assert "secret" not in response.text


async def test_readiness_times_out_slow_checks() -> None:
    settings = make_settings(health=HealthSettings(check_timeout_seconds=0.05))
    app = create_app(settings, health_checks={"database": _ok, "redis": _hang})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["redis"] == "timeout"


@pytest.mark.services
@pytest.mark.skipif(not os.getenv("RUN_SERVICE_TESTS"), reason="needs PostgreSQL and Redis")
async def test_readiness_against_real_services() -> None:
    settings = make_settings(
        database=DatabaseSettings(url=os.environ["DATABASE__URL"]),
        redis=RedisSettings(url=os.environ["REDIS__URL"]),
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok", "redis": "ok"}
