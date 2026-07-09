"""Smoke test fixtures — bootstrap DB once per session."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_smoke_database() -> None:
    from scripts.ci_bootstrap_db import main

    main()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as test_client:
        yield test_client


def login(client, username: str, password: str) -> dict:
    response = client.post(
        "/api/v1/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def refresh_token_from_response(
    client,
    response_json: dict,
    fallback: str,
    *,
    response=None,
) -> str:
    """Latest refresh token from JSON body or Set-Cookie (post-rotation)."""
    token = response_json.get("refresh_token")
    if token:
        return token
    if response is not None:
        cookie_token = response.cookies.get("refresh_token")
        if cookie_token:
            return cookie_token
    cookie_token = client.cookies.get("refresh_token")
    if cookie_token:
        return cookie_token
    return fallback
