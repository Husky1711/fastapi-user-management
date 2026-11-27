import os
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from tests.helpers import app_with, check_ok, client_for

APP_ENV_NAMES = frozenset({"ENVIRONMENT", "DEBUG", "APP_NAME", "VERSION"})
APP_ENV_PREFIXES = ("DATABASE__", "REDIS__", "JWT__", "CORS__", "LOG__", "HEALTH__")


@pytest.fixture(autouse=True)
def _isolate_from_shell_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must not depend on app settings exported in the developer's shell or in CI."""
    for name in list(os.environ):
        if name in APP_ENV_NAMES or name.startswith(APP_ENV_PREFIXES):
            monkeypatch.delenv(name)


@pytest.fixture
def app() -> FastAPI:
    return app_with(checks={"database": check_ok, "redis": check_ok})


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with client_for(app) as http:
        yield http
