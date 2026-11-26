"""Section 1.3: request ids, security headers, CORS and the access log."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from httpx import AsyncClient
from starlette.types import Receive, Scope, Send

from app.core.config import CorsSettings, Environment
from app.core.logging import JsonFormatter, request_id_var
from app.core.middleware import CLIENT_CLOSED_REQUEST, RequestContextMiddleware
from tests.helpers import (
    ALLOWED_ORIGIN,
    CRASH_PATH,
    RecordingSend,
    add_crash_route,
    app_with,
    client_for,
    http_scope,
    make_settings,
    receive_disconnect,
    strict_settings,
)

EXPECTED_CSP = "default-src 'none'; frame-ancestors 'none'"


def _cors_app() -> FastAPI:
    return app_with(make_settings(cors=CorsSettings(allow_origins=(ALLOWED_ORIGIN,))))


def _access_lines(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    return [
        json.loads(JsonFormatter().format(r)) for r in caplog.records if r.getMessage() == "request"
    ]


async def test_s1_3_08_request_id_is_generated_when_absent(client: AsyncClient) -> None:
    assert len((await client.get("/health/live")).headers["X-Request-ID"]) == 32


async def test_s1_3_09_valid_incoming_request_id_is_kept(client: AsyncClient) -> None:
    response = await client.get("/health/live", headers={"X-Request-ID": "abc-123.DEF_4"})
    assert response.headers["X-Request-ID"] == "abc-123.DEF_4"


@pytest.mark.parametrize("bad_id", ["", "has space", "x" * 65, "<script>", "a/b"])
async def test_s1_3_10_malformed_request_id_is_replaced(client: AsyncClient, bad_id: str) -> None:
    response = await client.get("/health/live", headers={"X-Request-ID": bad_id})
    assert response.headers["X-Request-ID"] not in (bad_id, "")


@pytest.mark.parametrize("good_id", ["a", "x" * 64])
async def test_s1_3_11_request_id_length_limits_are_inclusive(
    client: AsyncClient, good_id: str
) -> None:
    response = await client.get("/health/live", headers={"X-Request-ID": good_id})
    assert response.headers["X-Request-ID"] == good_id


async def test_s1_3_12_header_name_is_case_insensitive(client: AsyncClient) -> None:
    response = await client.get("/health/live", headers={"x-request-id": "lower-case-id"})
    assert response.headers["X-Request-ID"] == "lower-case-id"


async def test_s1_3_13_first_of_several_request_id_headers_is_used(client: AsyncClient) -> None:
    headers = [("X-Request-ID", "first-id"), ("X-Request-ID", "second-id")]
    response = await client.get("/health/live", headers=headers)
    assert response.headers["X-Request-ID"] == "first-id"


async def test_s1_3_14_non_ascii_request_id_is_replaced(client: AsyncClient) -> None:
    response = await client.get(
        "/health/live", headers={b"X-Request-ID": "caf\xe9-id".encode("latin-1")}
    )
    assert response.headers["X-Request-ID"] != "caf\xe9-id"
    assert response.headers["X-Request-ID"].isascii()


async def test_s1_3_15_concurrent_requests_never_share_request_ids(client: AsyncClient) -> None:
    ids = [f"req-{i}" for i in range(25)]
    responses = await asyncio.gather(
        *(client.get("/nope", headers={"X-Request-ID": rid}) for rid in ids)
    )
    for rid, response in zip(ids, responses, strict=True):
        assert response.headers["X-Request-ID"] == rid
        assert response.json()["request_id"] == rid


async def test_s1_3_16_one_access_log_line_per_request_and_no_secrets(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="app.core.middleware"):
        await client.get(
            "/health/live?token=query-secret",
            headers={"Authorization": "Bearer header-secret", "User-Agent": "tester/1.0"},
        )
    lines = _access_lines(caplog)
    assert len(lines) == 1
    line = lines[0]
    assert (line["method"], line["path"], line["status"]) == ("GET", "/health/live", 200)
    assert isinstance(line["duration_ms"], float)
    assert line["user_agent"] == "tester/1.0"
    assert "request_id" in line
    dumped = json.dumps(line)
    assert "header-secret" not in dumped
    assert "query-secret" not in dumped


async def test_s1_3_16_very_long_user_agent_is_truncated_in_logs(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="app.core.middleware"):
        await client.get("/health/live", headers={"User-Agent": "u" * 5000})
    assert len(str(_access_lines(caplog)[0]["user_agent"])) == 256


async def test_s1_3_17_security_headers_on_success(client: AsyncClient) -> None:
    headers = (await client.get("/health/live")).headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["Content-Security-Policy"] == EXPECTED_CSP
    assert "Strict-Transport-Security" not in headers


async def test_s1_3_18_security_headers_on_404_and_500() -> None:
    async with client_for(add_crash_route(_cors_app())) as client:
        for response in (await client.get("/nope"), await client.get(CRASH_PATH)):
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert response.headers["Content-Security-Policy"] == EXPECTED_CSP
            assert "X-Request-ID" in response.headers


async def test_s1_3_19_docs_page_is_exempt_from_the_api_csp(client: AsyncClient) -> None:
    docs = await client.get("/docs")
    assert docs.status_code == 200
    assert "Content-Security-Policy" not in docs.headers


@pytest.mark.parametrize("environment", [Environment.STAGING, Environment.PRODUCTION])
async def test_s1_3_20_strict_environments_send_hsts_and_hide_docs(
    environment: Environment,
) -> None:
    async with client_for(app_with(strict_settings(environment))) as client:
        live = await client.get("/health/live")
        docs = await client.get("/docs")
        schema = await client.get("/openapi.json")
    assert "max-age" in live.headers["Strict-Transport-Security"]
    assert (docs.status_code, schema.status_code) == (404, 404)


async def test_s1_3_21_cors_only_for_configured_origins() -> None:
    async with client_for(_cors_app()) as client:
        allowed = await client.get("/health/live", headers={"Origin": ALLOWED_ORIGIN})
        denied = await client.get("/health/live", headers={"Origin": "https://evil.example.com"})
    assert allowed.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "X-Request-ID" in allowed.headers["access-control-expose-headers"]
    assert "access-control-allow-origin" not in denied.headers


async def test_s1_3_22_cors_preflight_gets_request_id_and_security_headers() -> None:
    async with client_for(_cors_app()) as client:
        response = await client.options(
            "/health/live",
            headers={"Origin": ALLOWED_ORIGIN, "Access-Control-Request-Method": "GET"},
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"


async def test_s1_3_23_non_http_traffic_passes_through_untouched() -> None:
    seen: list[str] = []

    async def inner(scope: Scope, receive: Receive, send: Send) -> None:
        seen.append(scope["type"])

    await RequestContextMiddleware(inner)({"type": "lifespan"}, receive_disconnect, RecordingSend())
    assert seen == ["lifespan"]


async def test_s1_3_24_cancelled_request_is_logged_as_499_not_500(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def cancelled_app(scope: Scope, receive: Receive, send: Send) -> None:
        raise asyncio.CancelledError  # e.g. the server shutting down mid-request

    with (
        caplog.at_level(logging.INFO, logger="app.core.middleware"),
        pytest.raises(asyncio.CancelledError),
    ):
        await RequestContextMiddleware(cancelled_app)(
            http_scope(path="/slow"), receive_disconnect, RecordingSend()
        )
    assert _access_lines(caplog)[-1]["status"] == CLIENT_CLOSED_REQUEST


async def test_s1_3_29_client_disconnect_while_sending_body_is_499_without_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = app_with()

    @app.post("/_test/upload")
    async def upload(request: Request) -> None:
        await request.body()  # the client is gone: Starlette raises ClientDisconnect

    send = RecordingSend()
    with caplog.at_level(logging.INFO):
        await app(http_scope("POST", "/_test/upload"), receive_disconnect, send)
    assert send.messages == []  # nobody to answer
    assert _access_lines(caplog)[-1]["status"] == CLIENT_CLOSED_REQUEST
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


async def test_s1_3_30_request_id_does_not_leak_into_the_next_request_in_the_same_task(
    client: AsyncClient,
) -> None:
    # httpx's in-process transport runs the app in this very task, so a missing reset of the
    # request-id context would be visible here.
    await client.get("/health/live", headers={"X-Request-ID": "first-request"})
    assert request_id_var.get() is None


async def test_s1_3_31_failure_outside_the_error_boundary_gets_a_clean_500(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def broken_layer(scope: Scope, receive: Receive, send: Send) -> None:
        raise RuntimeError("middleware bug with secret-value")

    send = RecordingSend()
    with caplog.at_level(logging.INFO, logger="app.core.middleware"):
        await RequestContextMiddleware(broken_layer)(http_scope(), receive_disconnect, send)
    start = send.messages[0]
    assert start["status"] == 500
    headers = dict(start["headers"])
    assert b"x-request-id" in headers
    assert headers[b"content-type"] == b"application/problem+json"
    assert b"secret-value" not in b"".join(m.get("body", b"") for m in send.messages)
    errors = [r for r in caplog.records if r.getMessage() == "unhandled exception"]
    assert len(errors) == 1


async def test_s1_3_32_error_after_streaming_started_is_logged_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = app_with()

    async def broken_stream() -> AsyncIterator[bytes]:
        yield b"partial"
        raise RuntimeError("stream broke")

    @app.get("/_test/stream")
    async def stream() -> StreamingResponse:
        return StreamingResponse(broken_stream())

    async with client_for(app) as client:
        with caplog.at_level(logging.INFO), pytest.raises(RuntimeError):
            await client.get("/_test/stream")
    assert len([r for r in caplog.records if r.getMessage() == "unhandled exception"]) == 1
