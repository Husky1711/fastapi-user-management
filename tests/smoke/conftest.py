"""Smoke test fixtures — bootstrap DB once per session."""

from __future__ import annotations

import os

# CI-safe defaults must load before Settings is first imported.
if os.getenv("GITHUB_ACTIONS"):
    os.environ.setdefault("RATE_LIMIT__ENABLE_IP_LIMITS", "false")
    os.environ.setdefault("RATE_LIMIT__ENABLE_USER_LIMITS", "false")
    os.environ.setdefault("AUTH_COOKIE__USE_HTTPONLY_REFRESH", "false")
    os.environ.setdefault("AUTH_COOKIE__LEGACY_JSON_REFRESH", "true")

import pytest


@pytest.fixture(autouse=True)
def _clear_rate_limit_counters_before_test() -> None:
    """Avoid cross-test 429s when Redis counters persist within a session."""
    try:
        from utils.redis_config import RedisClient

        if RedisClient.test_connection():
            client = RedisClient.get_client()
            keys = list(client.scan_iter(match="rate_limit:*"))
            if keys:
                client.delete(*keys)
    except Exception:
        pass


@pytest.fixture(scope="session", autouse=True)
def _reset_rate_limit_counters() -> None:
    """Avoid cross-test 429s when Redis counters persist across pytest runs."""
    try:
        from utils.redis_config import RedisClient

        if RedisClient.test_connection():
            client = RedisClient.get_client()
            keys = list(client.scan_iter(match="rate_limit:*"))
            if keys:
                client.delete(*keys)
    except Exception:
        pass


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_smoke_database() -> None:
    if os.getenv("GITHUB_ACTIONS"):
        return
    from scripts.ci_bootstrap_db import main

    main()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as test_client:
        yield test_client


def login(client, username: str, password: str) -> dict:
    client.cookies.clear()
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
