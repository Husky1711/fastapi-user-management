import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import (
    CorsSettings,
    DatabaseSettings,
    Environment,
    JwtSettings,
    UnsafeConfigurationError,
)
from tests.helpers import SAFE_DB, SAFE_SECRET, make_settings


def production(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "environment": Environment.PRODUCTION,
        "jwt": JwtSettings(secret_key=SecretStr(SAFE_SECRET)),
        "database": SAFE_DB,
        "debug": False,
    }
    values.update(overrides)
    return values


def test_development_defaults_are_accepted() -> None:
    settings = make_settings(environment=Environment.DEVELOPMENT)
    assert settings.production_problems() == []
    settings.ensure_safe_for_production()
    assert settings.docs_enabled


def test_safe_production_settings_pass() -> None:
    settings = make_settings(**production())
    assert settings.production_problems() == []
    assert settings.is_production
    assert not settings.docs_enabled


def test_production_rejects_default_jwt_secret() -> None:
    settings = make_settings(**production(jwt=JwtSettings()))
    with pytest.raises(UnsafeConfigurationError, match="development default"):
        settings.ensure_safe_for_production()


def test_production_rejects_short_jwt_secret() -> None:
    settings = make_settings(**production(jwt=JwtSettings(secret_key=SecretStr("short"))))
    assert settings.production_problems() == ["JWT__SECRET_KEY must be at least 32 characters"]


def test_production_rejects_debug() -> None:
    settings = make_settings(**production(debug=True))
    assert settings.production_problems() == ["DEBUG must be false"]


def test_production_rejects_default_database_credentials() -> None:
    settings = make_settings(**production(database=DatabaseSettings()))
    assert len(settings.production_problems()) == 1
    assert "postgres:postgres" in settings.production_problems()[0]


def test_production_reports_every_problem_at_once() -> None:
    settings = make_settings(
        **production(jwt=JwtSettings(), debug=True, database=DatabaseSettings())
    )
    with pytest.raises(UnsafeConfigurationError) as exc_info:
        settings.ensure_safe_for_production()
    assert len(exc_info.value.problems) == 3


def test_cors_wildcard_with_credentials_is_rejected_everywhere() -> None:
    with pytest.raises(ValidationError, match="cannot be combined"):
        CorsSettings(allow_origins=["*"], allow_credentials=True)


def test_cors_wildcard_without_credentials_is_allowed() -> None:
    cors = CorsSettings(allow_origins=["*"], allow_credentials=False)
    assert cors.allow_origins == ["*"]


def test_nested_settings_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE__POOL_SIZE", "7")
    monkeypatch.setenv("CORS__ALLOW_ORIGINS", '["https://app.example.com"]')
    settings = make_settings()
    assert settings.database.pool_size == 7
    assert settings.cors.allow_origins == ["https://app.example.com"]


def test_secret_is_not_shown_in_repr() -> None:
    settings = make_settings(jwt=JwtSettings(secret_key=SecretStr(SAFE_SECRET)))
    assert SAFE_SECRET not in repr(settings)
