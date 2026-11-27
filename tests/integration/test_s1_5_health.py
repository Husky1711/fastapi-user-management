"""Section 1.5: health endpoints, app lifespan and real services."""

import asyncio
import logging
import os

import pytest
from httpx import AsyncClient

import app.main as main_module
from app.core.config import DatabaseSettings, HealthSettings, RedisSettings
from app.core.logging import JsonFormatter
from tests.helpers import app_with, check_never_finishes, check_ok, client_for, make_settings

# Read at import time: the autouse fixture clears app settings from the environment per test.
SERVICE_DATABASE_URL = os.getenv("DATABASE__URL", "")
SERVICE_REDIS_URL = os.getenv("REDIS__URL", "")


async def _fails_with_secret() -> None:
    raise ConnectionError("postgresql://user:secret@db/app refused")


async def test_s1_5_01_liveness(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert (response.status_code, response.json()) == (200, {"status": "alive"})


async def test_s1_5_02_readiness_when_all_checks_pass(client: AsyncClient) -> None:
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}


async def test_s1_5_03_failed_check_gives_503_without_leaking_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = app_with(checks={"database": _fails_with_secret, "redis": check_ok})
    async with client_for(app) as client:
        with caplog.at_level(logging.INFO):
            response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "error", "redis": "ok"},
    }
    assert "secret" not in response.text
    failures = [r for r in caplog.records if r.getMessage() == "readiness check failed"]
    assert len(failures) == 1
    assert not failures[0].exc_info  # no traceback in the logs...
    assert not failures[0].exc_text  # ...not even pre-rendered
    # Check the JSON lines exactly as they are written in production, fields included.
    written = "\n".join(JsonFormatter().format(r) for r in caplog.records)
    assert '"error_type": "ConnectionError"' in written
    assert "postgresql://***@db/app refused" in written
    assert "secret" not in written


async def test_s1_5_04_hanging_check_gives_503_timeout() -> None:
    settings = make_settings(health=HealthSettings(check_timeout_seconds=0.05))
    app = app_with(settings, {"database": check_ok, "redis": check_never_finishes})
    async with client_for(app) as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["redis"] == "timeout"


async def test_s1_5_06_many_concurrent_probes_all_answer(client: AsyncClient) -> None:
    responses = await asyncio.gather(*(client.get("/health/ready") for _ in range(30)))
    assert {r.status_code for r in responses} == {200}


async def test_s1_5_08_docs_list_the_health_routes(client: AsyncClient) -> None:
    paths = (await client.get("/openapi.json")).json()["paths"]
    assert {"/health/live", "/health/ready"} <= set(paths)


class _FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class _FakeRedis:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


def _fake_resources(monkeypatch: pytest.MonkeyPatch) -> tuple[list[_FakeEngine], list[_FakeRedis]]:
    engines: list[_FakeEngine] = []
    clients: list[_FakeRedis] = []

    def fake_engine(_: object) -> _FakeEngine:
        engines.append(_FakeEngine())
        return engines[-1]

    def fake_redis(_: object) -> _FakeRedis:
        clients.append(_FakeRedis())
        return clients[-1]

    monkeypatch.setattr(main_module, "create_engine", fake_engine)
    monkeypatch.setattr(main_module, "create_redis", fake_redis)
    return engines, clients


async def test_s1_5_09_lifespan_builds_default_checks_and_closes_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engines, clients = _fake_resources(monkeypatch)
    app = main_module.create_app(make_settings())

    async with app.router.lifespan_context(app):
        assert app.state.readiness.check_names == ("database", "redis")
    assert engines[0].disposed
    assert clients[0].closed


async def test_s1_5_10_second_lifespan_rebinds_checks_to_new_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engines, clients = _fake_resources(monkeypatch)
    app = main_module.create_app(make_settings())
    async with app.router.lifespan_context(app):
        first_probe = app.state.readiness
    async with app.router.lifespan_context(app):
        assert app.state.readiness is not first_probe
        assert app.state.engine is engines[1]
    assert (len(engines), engines[1].disposed, clients[1].closed) == (2, True, True)


async def test_s1_5_16_no_checks_means_not_ready() -> None:
    async with client_for(app_with()) as client:  # lifespan not started: nothing checked
        response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "checks": {}}


async def test_s1_5_17_thirty_concurrent_probes_over_http_run_the_checks_once() -> None:
    calls = 0
    entered, release = asyncio.Event(), asyncio.Event()

    async def counting_check() -> None:
        nonlocal calls
        calls += 1
        entered.set()
        await release.wait()

    app = app_with(checks={"database": counting_check})
    async with client_for(app) as client:
        pending = [asyncio.create_task(client.get("/health/ready")) for _ in range(30)]
        await entered.wait()  # the first probe is inside the check; the rest queue or hit the cache
        release.set()
        responses = await asyncio.gather(*pending)
    assert calls == 1
    assert {r.status_code for r in responses} == {200}


@pytest.mark.services
@pytest.mark.skipif(not os.getenv("RUN_SERVICE_TESTS"), reason="needs PostgreSQL and Redis")
async def test_s1_5_11_readiness_against_real_postgres_and_redis() -> None:
    settings = make_settings(
        database=DatabaseSettings(url=SERVICE_DATABASE_URL),
        redis=RedisSettings(url=SERVICE_REDIS_URL),
    )
    app = main_module.create_app(settings)
    async with app.router.lifespan_context(app), client_for(app) as client:
        response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok", "redis": "ok"}
