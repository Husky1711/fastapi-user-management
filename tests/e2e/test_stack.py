"""Milestone gate, check 3 (user): scenarios against the real running stack.

Runs only when E2E_BASE_URL is set, e.g. in CI after `docker compose up`:
    E2E_BASE_URL=http://localhost:8000 uv run pytest tests/e2e --no-cov
"""

import os
import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient

BASE_URL = os.getenv("E2E_BASE_URL", "")

pytestmark = pytest.mark.skipif(not BASE_URL, reason="set E2E_BASE_URL to run e2e tests")


@pytest.fixture
async def http() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(base_url=BASE_URL, timeout=10) as client:
        yield client


# U1 — an operator's load balancer sees the service as alive and ready
async def test_u1_service_is_alive_and_ready(http: AsyncClient) -> None:
    assert (await http.get("/health/live")).json() == {"status": "alive"}
    ready = await http.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}


# U2 — a frontend developer can open the API docs and find the endpoints
async def test_u2_api_docs_are_available(http: AsyncClient) -> None:
    assert (await http.get("/docs")).status_code == 200
    paths = (await http.get("/openapi.json")).json()["paths"]
    assert {"/health/live", "/health/ready"} <= set(paths)


# U3 — a client calling a wrong URL gets a clear, machine-readable error it can report
async def test_u3_wrong_url_gives_problem_json(http: AsyncClient) -> None:
    response = await http.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["code"] == "http.not_found"
    assert body["request_id"] == response.headers["X-Request-ID"]


# U4 — a client can trace its own request id through the system
async def test_u4_request_id_round_trip(http: AsyncClient) -> None:
    rid = uuid.uuid4().hex
    response = await http.get("/health/live", headers={"X-Request-ID": rid})
    assert response.headers["X-Request-ID"] == rid


# U5 — the real server sends security headers
async def test_u5_security_headers_on_real_server(http: AsyncClient) -> None:
    headers = (await http.get("/health/live")).headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
