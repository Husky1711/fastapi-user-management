from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from tests.helpers import app_with, check_ok, client_for


@pytest.fixture
def app() -> FastAPI:
    return app_with(checks={"database": check_ok, "redis": check_ok})


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with client_for(app) as http:
        yield http
