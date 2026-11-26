"""Error format (RFC 9457), request ids and security headers.

Test-only routes are added to a fresh app inside the test; they never exist in the real app.
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, SecretStr

from app.core.config import CorsSettings, Environment, JwtSettings
from app.core.errors import Conflict, NotFound
from app.main import create_app
from tests.helpers import SAFE_DB, SAFE_SECRET, make_settings


class SignupIn(BaseModel):
    email: str
    password: str


def _app_with_test_routes() -> FastAPI:
    app = create_app(make_settings(), health_checks={})

    @app.get("/_test/not-found")
    async def not_found() -> None:
        raise NotFound("User 42 does not exist.", code="user.not_found")

    @app.get("/_test/conflict")
    async def conflict() -> None:
        raise Conflict(headers={"X-Extra": "1"})

    @app.post("/_test/signup")
    async def signup(body: SignupIn) -> None:
        return None

    @app.get("/_test/crash")
    async def crash() -> None:
        raise RuntimeError("database password is hunter2")

    return app


@pytest.fixture
async def test_client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=_app_with_test_routes())
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


def _assert_problem(response_json: dict[str, object], status: int, code: str) -> None:
    assert response_json["status"] == status
    assert response_json["code"] == code
    assert response_json["type"] == "about:blank"
    assert isinstance(response_json["title"], str)
    assert isinstance(response_json["request_id"], str)


async def test_app_error_becomes_problem_json(test_client: AsyncClient) -> None:
    response = await test_client.get("/_test/not-found")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    _assert_problem(body, 404, "user.not_found")
    assert body["detail"] == "User 42 does not exist."
    assert body["request_id"] == response.headers["X-Request-ID"]


async def test_app_error_defaults_and_headers(test_client: AsyncClient) -> None:
    response = await test_client.get("/_test/conflict")
    assert response.status_code == 409
    assert response.headers["X-Extra"] == "1"
    _assert_problem(response.json(), 409, "resource.conflict")


async def test_validation_error_lists_fields_without_echoing_input(
    test_client: AsyncClient,
) -> None:
    response = await test_client.post("/_test/signup", json={"password": "hunter2"})
    assert response.status_code == 422
    body = response.json()
    _assert_problem(body, 422, "request.validation_failed")
    assert body["errors"] == [
        {"loc": ["body", "email"], "message": "Field required", "type": "missing"}
    ]
    assert "hunter2" not in response.text


async def test_unknown_route_is_problem_json(test_client: AsyncClient) -> None:
    response = await test_client.get("/nope")
    assert response.status_code == 404
    _assert_problem(response.json(), 404, "http.not_found")


async def test_wrong_method_is_problem_json(test_client: AsyncClient) -> None:
    response = await test_client.delete("/health/live")
    assert response.status_code == 405
    _assert_problem(response.json(), 405, "http.method_not_allowed")


async def test_unhandled_exception_is_generic_500(test_client: AsyncClient) -> None:
    response = await test_client.get("/_test/crash")
    assert response.status_code == 500
    _assert_problem(response.json(), 500, "server.internal_error")
    assert "hunter2" not in response.text
    assert response.headers["X-Request-ID"] == response.json()["request_id"]


async def test_request_id_is_generated(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert len(response.headers["X-Request-ID"]) == 32


async def test_valid_incoming_request_id_is_kept(client: AsyncClient) -> None:
    response = await client.get("/health/live", headers={"X-Request-ID": "abc-123.DEF_4"})
    assert response.headers["X-Request-ID"] == "abc-123.DEF_4"


@pytest.mark.parametrize("bad_id", ["has space", "x" * 65, "<script>"])
async def test_malformed_incoming_request_id_is_replaced(client: AsyncClient, bad_id: str) -> None:
    response = await client.get("/health/live", headers={"X-Request-ID": bad_id})
    assert response.headers["X-Request-ID"] != bad_id


async def test_security_headers(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "Strict-Transport-Security" not in response.headers


async def test_production_adds_hsts_and_hides_docs() -> None:
    settings = make_settings(
        environment=Environment.PRODUCTION,
        jwt=JwtSettings(secret_key=SecretStr(SAFE_SECRET)),
        database=SAFE_DB,
    )
    app = create_app(settings, health_checks={})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        live = await client.get("/health/live")
        docs = await client.get("/docs")
    assert "max-age" in live.headers["Strict-Transport-Security"]
    assert docs.status_code == 404


async def test_docs_are_served_outside_production(client: AsyncClient) -> None:
    assert (await client.get("/openapi.json")).status_code == 200


async def test_cors_allows_only_configured_origins() -> None:
    settings = make_settings(cors=CorsSettings(allow_origins=["https://app.example.com"]))
    app = create_app(settings, health_checks={})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        allowed = await client.get("/health/live", headers={"Origin": "https://app.example.com"})
        denied = await client.get("/health/live", headers={"Origin": "https://evil.example.com"})
    assert allowed.headers["access-control-allow-origin"] == "https://app.example.com"
    assert "access-control-allow-origin" not in denied.headers


def test_unsafe_production_settings_stop_startup() -> None:
    with pytest.raises(RuntimeError, match="Unsafe production configuration"):
        create_app(make_settings(environment=Environment.PRODUCTION), health_checks={})
