"""Section 1.2: settings as the running app sees them."""

import pytest

from app import __version__
from app.core.config import Environment
from tests.helpers import app_with, client_for, make_settings


def test_s1_2_16_unrelated_version_env_var_cannot_change_the_app_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VERSION", "9.9.9")
    assert app_with().version == __version__


@pytest.mark.parametrize("environment", [Environment.STAGING, Environment.PRODUCTION])
def test_s1_2_19_app_refuses_to_start_with_unsafe_settings(environment: Environment) -> None:
    with pytest.raises(RuntimeError, match=f"Unsafe configuration for {environment}"):
        app_with(make_settings(environment=environment))


async def test_s1_2_16_version_is_published_in_the_api_schema() -> None:
    async with client_for(app_with()) as client:
        info = (await client.get("/openapi.json")).json()["info"]
    assert info["version"] == __version__
