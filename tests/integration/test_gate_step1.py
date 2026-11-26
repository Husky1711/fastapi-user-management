"""Milestone 1 gate, check 2 (tester): edge cases and attacks not covered elsewhere.

Each test maps to a row in docs/milestones/step-1.md, section 2.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from httpx import ASGITransport, AsyncClient
from starlette.types import Message, Receive, Scope, Send

from app.core.config import CorsSettings, Environment, Settings
from app.core.logging import JsonFormatter
from app.core.middleware import RequestContextMiddleware
from app.main import create_app
from tests.helpers import make_settings


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# T1 — production is detected from real environment variables, not only from code
def test_t1_production_from_environment_variables_is_unsafe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("JWT__SECRET_KEY", raising=False)
    settings = Settings(_env_file=None)
    assert settings.environment is Environment.PRODUCTION
    assert "JWT__SECRET_KEY is the development default" in settings.production_problems()


# T2 — CORS preflight from an allowed origin still gets a request id and security headers
async def test_t2_cors_preflight_gets_request_id_and_security_headers() -> None:
    settings = make_settings(cors=CorsSettings(allow_origins=["https://app.example.com"]))
    async with _client(create_app(settings, health_checks={})) as client:
        response = await client.options(
            "/health/live",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://app.example.com"
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"


# T3 — exactly one access log line per request, with timing, and no request headers in it
async def test_t3_one_log_line_per_request_without_secrets(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async with _client(create_app(make_settings(), health_checks={})) as client:
        caplog.clear()
        with caplog.at_level(logging.INFO, logger="app.core.middleware"):
            await client.get("/health/live", headers={"Authorization": "Bearer top-secret-token"})
    lines = [
        json.loads(JsonFormatter().format(r)) for r in caplog.records if r.getMessage() == "request"
    ]
    assert len(lines) == 1
    line = lines[0]
    assert (line["method"], line["path"], line["status"]) == ("GET", "/health/live", 200)
    assert isinstance(line["duration_ms"], float)
    assert "request_id" in line
    assert "top-secret-token" not in json.dumps(line)


# T4 — the request id header is matched case-insensitively
async def test_t4_lowercase_request_id_header_is_honoured(client: AsyncClient) -> None:
    response = await client.get("/health/live", headers={"x-request-id": "lower-case-id"})
    assert response.headers["X-Request-ID"] == "lower-case-id"


# T5 — concurrent requests never see each other's request id
async def test_t5_request_ids_do_not_leak_between_concurrent_requests(
    client: AsyncClient,
) -> None:
    ids = [f"req-{i}" for i in range(25)]
    responses = await asyncio.gather(
        *(client.get("/nope", headers={"X-Request-ID": rid}) for rid in ids)
    )
    for rid, response in zip(ids, responses, strict=True):
        assert response.headers["X-Request-ID"] == rid
        assert response.json()["request_id"] == rid


# T6 — an error after the response has started cannot become a clean 500; it must surface
async def test_t6_error_mid_stream_is_not_swallowed() -> None:
    app = create_app(make_settings(), health_checks={})

    async def broken_stream() -> AsyncIterator[bytes]:
        yield b"partial"
        raise RuntimeError("stream broke")

    @app.get("/_test/stream")
    async def stream() -> StreamingResponse:
        return StreamingResponse(broken_stream())

    async with _client(app) as client:
        with pytest.raises(RuntimeError, match="stream broke"):
            await client.get("/_test/stream")


# T7 — an HTTPException with a non-text detail falls back to the standard description
async def test_t7_http_exception_with_structured_detail() -> None:
    app = create_app(make_settings(), health_checks={})

    @app.get("/_test/teapot")
    async def teapot() -> None:
        raise HTTPException(status_code=418, detail={"internal": "do not show"})

    async with _client(app) as client:
        response = await client.get("/_test/teapot")
    assert response.status_code == 418
    assert response.json()["code"] == "http.im_a_teapot"
    assert "do not show" not in response.text


# T8 — non-HTTP traffic (lifespan, websockets) passes through the middleware untouched
async def test_t8_non_http_scopes_pass_through() -> None:
    seen: list[str] = []

    async def inner(scope: Scope, receive: Receive, send: Send) -> None:
        seen.append(scope["type"])

    async def receive() -> Message:
        return {"type": "lifespan.startup"}

    async def send(message: Message) -> None:
        return None

    middleware = RequestContextMiddleware(inner)
    await middleware({"type": "lifespan"}, receive, send)
    assert seen == ["lifespan"]
