"""Section 3.7: a whole auth flow leaves no password, token or full email in the logs."""

import logging
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.logging import JsonFormatter
from tests.api import api_client
from tests.db import SERVICES

pytestmark = SERVICES
LOGIN = "/api/v1/auth/login"


async def test_s3_7_07_login_and_refresh_never_log_passwords_or_tokens(
    db_connection: AsyncConnection, caplog: pytest.LogCaptureFixture
) -> None:
    email = f"logs-{uuid.uuid4().hex[:12]}@example.com"
    password = "Never-Logged-Passw0rd"
    with caplog.at_level(logging.DEBUG):
        async with api_client(db_connection) as http:
            await http.post("/api/v1/auth/signup", json={"email": email, "password": password})
            await http.post(LOGIN, json={"email": email, "password": "Wrong-Passw0rd-123"})
            tokens = (await http.post(LOGIN, json={"email": email, "password": password})).json()
            await http.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
            await http.post(
                "/api/v1/auth/logout", headers={"Authorization": f"Bearer {tokens['access_token']}"}
            )
    logged = "\n".join(JsonFormatter().format(r) for r in caplog.records)
    for secret in (
        password,
        "Wrong-Passw0rd-123",
        tokens["refresh_token"],
        tokens["access_token"],
        email,
    ):
        assert secret not in logged
