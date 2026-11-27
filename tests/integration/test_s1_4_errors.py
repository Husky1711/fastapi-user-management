"""Section 1.4: one error format (RFC 9457) for every failure.

Test-only routes are added to a fresh app inside the test; they never exist in the real app.
"""

from collections.abc import AsyncIterator, Mapping

import pytest
from fastapi import APIRouter, FastAPI, HTTPException, Query
from httpx import AsyncClient
from pydantic import BaseModel

from app.core.config import CorsSettings
from app.core.errors import Conflict, NotFound
from app.main import create_app
from tests.helpers import (
    ALLOWED_ORIGIN,
    CRASH_PATH,
    CRASH_SECRET,
    STREAM_PATH,
    add_broken_stream_route,
    add_crash_route,
    app_with,
    client_for,
    make_settings,
)


class SignupIn(BaseModel):
    email: str
    password: str


def _app_with_test_routes() -> FastAPI:
    app = add_broken_stream_route(
        add_crash_route(app_with(make_settings(cors=CorsSettings(allow_origins=(ALLOWED_ORIGIN,)))))
    )

    @app.get("/_test/not-found")
    async def not_found() -> None:
        raise NotFound("User 42 does not exist.", code="user.not_found")

    @app.get("/_test/conflict")
    async def conflict() -> None:
        raise Conflict(headers={"X-Extra": "1"})

    @app.post("/_test/signup")
    async def signup(body: SignupIn) -> None:
        return None

    @app.get("/_test/items")
    async def items(limit: int = Query(ge=1, le=100)) -> None:
        return None

    @app.post("/_test/scores")
    async def scores(body: dict[str, int]) -> None:
        return None

    @app.get("/_test/teapot")
    async def teapot() -> None:
        raise HTTPException(status_code=418, detail={"internal": "do not show"})

    @app.get("/_test/client-closed")
    async def client_closed() -> None:
        raise HTTPException(status_code=499, detail="Client closed request")

    return app


@pytest.fixture
async def http() -> AsyncIterator[AsyncClient]:
    async with client_for(_app_with_test_routes()) as client:
        yield client


def _assert_problem(body: Mapping[str, object], status: int, code: str) -> None:
    assert body["status"] == status
    assert body["code"] == code
    assert body["type"] == "about:blank"
    assert isinstance(body["title"], str)
    assert isinstance(body["request_id"], str)


async def test_s1_4_01_app_error_becomes_problem_json(http: AsyncClient) -> None:
    response = await http.get("/_test/not-found")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    _assert_problem(body, 404, "user.not_found")
    assert body["detail"] == "User 42 does not exist."
    assert body["request_id"] == response.headers["X-Request-ID"]


async def test_s1_4_02_defaults_and_custom_headers(http: AsyncClient) -> None:
    response = await http.get("/_test/conflict")
    assert response.status_code == 409
    assert response.headers["X-Extra"] == "1"
    _assert_problem(response.json(), 409, "resource.conflict")


async def test_s1_4_03_validation_lists_fields_without_echoing_input(http: AsyncClient) -> None:
    response = await http.post("/_test/signup", json={"password": "hunter2"})
    assert response.status_code == 422
    body = response.json()
    _assert_problem(body, 422, "request.validation_failed")
    assert body["errors"] == [
        {"loc": ["body", "email"], "message": "Field required", "type": "missing"}
    ]
    assert "hunter2" not in response.text


async def test_s1_4_04_malformed_json_body_is_rejected_without_echo(http: AsyncClient) -> None:
    response = await http.post(
        "/_test/signup",
        content=b'{"email": "a@b.c", "password": "hunter2"',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    body = response.json()
    _assert_problem(body, 422, "request.validation_failed")
    assert body["errors"][0]["type"] == "json_invalid"
    assert "hunter2" not in response.text


@pytest.mark.parametrize("value", ["0", "101", "abc"])
async def test_s1_4_05_query_parameter_errors_point_at_the_parameter(
    http: AsyncClient, value: str
) -> None:
    response = await http.get("/_test/items", params={"limit": value})
    assert response.status_code == 422
    assert response.json()["errors"][0]["loc"] == ["query", "limit"]


async def test_s1_4_06_unknown_route_is_problem_json(http: AsyncClient) -> None:
    response = await http.get("/nope")
    assert response.status_code == 404
    _assert_problem(response.json(), 404, "http.not_found")


async def test_s1_4_07_wrong_method_is_problem_json(http: AsyncClient) -> None:
    response = await http.delete("/health/live")
    assert response.status_code == 405
    _assert_problem(response.json(), 405, "http.method_not_allowed")


async def test_s1_4_08_unhandled_exception_is_a_generic_500(http: AsyncClient) -> None:
    response = await http.get(CRASH_PATH)
    assert response.status_code == 500
    _assert_problem(response.json(), 500, "server.internal_error")
    assert CRASH_SECRET not in response.text
    assert response.headers["X-Request-ID"] == response.json()["request_id"]


async def test_s1_4_09_structured_http_exception_detail_is_hidden(http: AsyncClient) -> None:
    response = await http.get("/_test/teapot")
    assert response.status_code == 418
    assert response.json()["code"] == "http.im_a_teapot"
    assert "do not show" not in response.text


async def test_s1_4_10_non_standard_status_code_still_gets_problem_json(
    http: AsyncClient,
) -> None:
    response = await http.get("/_test/client-closed")
    assert response.status_code == 499
    body = response.json()
    _assert_problem(body, 499, "http.499")
    assert body["title"] == "Error"


async def test_s1_4_11_error_after_streaming_started_is_not_disguised(http: AsyncClient) -> None:
    with pytest.raises(RuntimeError, match="stream broke"):
        await http.get(STREAM_PATH)


async def test_s1_4_12_browser_can_read_a_500_from_an_allowed_origin(http: AsyncClient) -> None:
    response = await http.get(CRASH_PATH, headers={"Origin": ALLOWED_ORIGIN})
    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


async def test_s1_4_16_client_chosen_keys_in_error_paths_are_cut_short(http: AsyncClient) -> None:
    long_key = "k" * 500
    response = await http.post("/_test/scores", json={long_key: "not-a-number-secret"})
    assert response.status_code == 422
    loc = response.json()["errors"][0]["loc"]
    assert loc == ["body", "k" * 64 + "…"]
    assert "not-a-number-secret" not in response.text
    assert long_key not in response.text


async def test_s1_4_17_error_responses_are_documented_as_problem_json_only(
    http: AsyncClient,
) -> None:
    schema = (await http.get("/openapi.json")).json()
    components = schema["components"]["schemas"]
    assert {"ProblemOut", "ValidationProblemOut", "FieldError"} <= set(components)
    expected = {"type", "title", "status", "detail", "code", "request_id"}
    assert set(components["ProblemOut"]["properties"]) >= expected
    ready = schema["paths"]["/health/ready"]["get"]["responses"]
    assert set(ready["500"]["content"]) == {"application/problem+json"}
    assert "503" in ready


class EchoIn(BaseModel):
    name: str


async def test_s1_4_18_versioned_api_routes_document_422_and_500_as_problem_json() -> None:
    feature = APIRouter()

    @feature.post("/_test/echo")
    async def echo(body: EchoIn) -> EchoIn:
        return body

    async with client_for(create_app(make_settings(), api_routers=[feature])) as client:
        schema = (await client.get("/openapi.json")).json()
        invalid = await client.post("/api/v1/_test/echo", json={})
    responses = schema["paths"]["/api/v1/_test/echo"]["post"]["responses"]
    assert set(responses["422"]["content"]) == {"application/problem+json"}
    assert responses["422"]["content"]["application/problem+json"]["schema"] == {
        "$ref": "#/components/schemas/ValidationProblemOut"
    }
    assert set(responses["500"]["content"]) == {"application/problem+json"}
    assert invalid.status_code == 422
    assert invalid.headers["content-type"] == "application/problem+json"
