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
