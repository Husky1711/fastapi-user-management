"""Real-user scenarios against the running stack (gate check 3).

Runs only when E2E_BASE_URL is set, e.g. in CI after `docker compose up`:
    E2E_BASE_URL=http://localhost:8000 E2E_ALLOWED_ORIGIN=http://localhost:3000 \\
        uv run pytest tests/e2e --no-cov
"""

import os
import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient

BASE_URL = os.getenv("E2E_BASE_URL", "")
ALLOWED_ORIGIN = os.getenv("E2E_ALLOWED_ORIGIN", "")

pytestmark = pytest.mark.skipif(not BASE_URL, reason="set E2E_BASE_URL to run e2e tests")


@pytest.fixture
async def http() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(base_url=BASE_URL, timeout=10) as client:
        yield client


async def test_s1_5_12_operator_sees_service_alive_and_ready(http: AsyncClient) -> None:
    assert (await http.get("/health/live")).json() == {"status": "alive"}
    ready = await http.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}


async def test_s1_5_08_frontend_developer_finds_the_api_docs(http: AsyncClient) -> None:
    assert (await http.get("/docs")).status_code == 200
    paths = (await http.get("/openapi.json")).json()["paths"]
    assert {"/health/live", "/health/ready"} <= set(paths)


async def test_s1_4_13_client_gets_problem_json_for_a_wrong_url(http: AsyncClient) -> None:
    response = await http.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["code"] == "http.not_found"
    assert body["request_id"] == response.headers["X-Request-ID"]


@pytest.mark.skipif(not ALLOWED_ORIGIN, reason="set E2E_ALLOWED_ORIGIN")
async def test_s1_4_14_browser_app_can_read_errors_and_their_request_id(http: AsyncClient) -> None:
    response = await http.get("/api/v1/does-not-exist", headers={"Origin": ALLOWED_ORIGIN})
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "x-request-id" in response.headers["access-control-expose-headers"].lower()
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


async def test_s1_3_25_client_traces_its_own_request_id(http: AsyncClient) -> None:
    rid = uuid.uuid4().hex
    assert (await http.get("/health/live", headers={"X-Request-ID": rid})).headers[
        "X-Request-ID"
    ] == rid


async def test_s1_3_26_real_server_sends_security_headers(http: AsyncClient) -> None:
    headers = (await http.get("/health/live")).headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"
