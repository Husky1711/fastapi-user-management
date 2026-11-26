"""Section 1.2: settings and safety checks for strict environments."""

import pytest
from pydantic import SecretStr, ValidationError
from pydantic_settings import SettingsError

from app.core.config import (
    MIN_JWT_SECRET_LENGTH,
    CorsSettings,
    DatabaseSettings,
    Environment,
    JwtSettings,
    Settings,
    UnsafeConfigurationError,
    get_settings,
)
from tests.helpers import make_settings, strict_settings


def test_s1_2_01_development_defaults_are_accepted_with_docs() -> None:
    settings = make_settings(environment=Environment.DEVELOPMENT)
    assert settings.safety_problems() == []
    settings.ensure_safe()
    assert settings.docs_enabled


@pytest.mark.parametrize("environment", [Environment.STAGING, Environment.PRODUCTION])
def test_s1_2_02_safe_strict_settings_pass_without_docs(environment: Environment) -> None:
    settings = strict_settings(environment)
    assert settings.safety_problems() == []
    assert settings.is_strict
    assert not settings.docs_enabled


@pytest.mark.parametrize("environment", [Environment.STAGING, Environment.PRODUCTION])
def test_s1_2_03_default_jwt_secret_is_rejected(environment: Environment) -> None:
    with pytest.raises(UnsafeConfigurationError, match="development default"):
        strict_settings(environment, jwt=JwtSettings()).ensure_safe()


@pytest.mark.parametrize(
    ("length", "accepted"),
    [
        (MIN_JWT_SECRET_LENGTH - 1, False),
        (MIN_JWT_SECRET_LENGTH, True),
        (MIN_JWT_SECRET_LENGTH + 1, True),
    ],
)
def test_s1_2_04_jwt_secret_length_boundary(length: int, accepted: bool) -> None:
    settings = strict_settings(jwt=JwtSettings(secret_key=SecretStr("k" * length)))
    expected = [] if accepted else ["JWT__SECRET_KEY must be at least 32 characters"]
    assert settings.safety_problems() == expected


def test_s1_2_05_debug_is_rejected() -> None:
    assert strict_settings(debug=True).safety_problems() == ["DEBUG must be false"]


def test_s1_2_06_default_database_credentials_are_rejected() -> None:
    problems = strict_settings(database=DatabaseSettings()).safety_problems()
    assert len(problems) == 1
    assert "postgres:postgres" in problems[0]


def test_s1_2_07_every_problem_is_reported_at_once() -> None:
    settings = strict_settings(jwt=JwtSettings(), debug=True, database=DatabaseSettings())
    with pytest.raises(UnsafeConfigurationError) as exc_info:
        settings.ensure_safe()
    assert len(exc_info.value.problems) == 3


@pytest.mark.parametrize("environment", [Environment.DEVELOPMENT, Environment.TEST])
def test_s1_2_08_relaxed_environments_skip_the_checks(environment: Environment) -> None:
    settings = make_settings(environment=environment, jwt=JwtSettings(), debug=True)
    assert settings.safety_problems() == []


def test_s1_2_09_cors_wildcard_with_credentials_is_rejected() -> None:
    with pytest.raises(ValidationError, match="cannot be combined"):
        CorsSettings(allow_origins=("*",), allow_credentials=True)


def test_s1_2_10_cors_wildcard_is_allowed_only_without_credentials() -> None:
    assert CorsSettings(allow_origins=("*",), allow_credentials=False).allow_origins == ("*",)


def test_s1_2_11_nested_values_and_json_lists_load_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE__POOL_SIZE", "7")
    monkeypatch.setenv("CORS__ALLOW_ORIGINS", '["https://app.example.com"]')
    settings = make_settings()
    assert settings.database.pool_size == 7
    assert settings.cors.allow_origins == ("https://app.example.com",)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("ENVIRONMENT", "prod"),
        ("DATABASE__POOL_SIZE", "0"),
        ("DATABASE__POOL_SIZE", "101"),
        ("DATABASE__POOL_SIZE", "five"),
        ("LOG__LEVEL", "verbose"),
        ("CORS__ALLOW_ORIGINS", "[not json"),
        ("JWT__ALGORITHM", "none"),
        ("JWT__ALGORITHM", "RS256"),
        ("HEALTH__CHECK_TIMEOUT_SECONDS", "0"),
        ("DATABASE__UNKNOWN_OPTION", "1"),
    ],
)
def test_s1_2_12_invalid_env_values_stop_startup(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises((ValidationError, SettingsError)):
        Settings(_env_file=None)


@pytest.mark.parametrize("size", [1, 100])
def test_s1_2_13_pool_size_limits_are_inclusive(size: int) -> None:
    assert DatabaseSettings(pool_size=size).pool_size == size


def test_s1_2_14_secret_is_not_shown_when_settings_are_printed() -> None:
    secret = "super-secret-value-that-must-not-leak-0001"
    settings = make_settings(jwt=JwtSettings(secret_key=SecretStr(secret)))
    assert secret not in repr(settings)
    assert secret not in str(settings.model_dump())


def test_s1_2_15_production_from_real_env_vars_is_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("JWT__SECRET_KEY", raising=False)
    settings = Settings(_env_file=None)
    assert settings.environment is Environment.PRODUCTION
    assert "JWT__SECRET_KEY is the development default" in settings.safety_problems()


def test_s1_2_17_jwt_algorithm_is_limited_to_hmac() -> None:
    assert JwtSettings(algorithm="HS512").algorithm == "HS512"


def _assign(target: object, name: str, value: object) -> None:
    setattr(target, name, value)


def test_s1_2_18_settings_cannot_be_changed_after_the_safety_check() -> None:
    settings = strict_settings()
    with pytest.raises(ValidationError, match="frozen"):
        _assign(settings.database, "url", "postgresql+asyncpg://postgres:postgres@db/app")
    with pytest.raises(ValidationError, match="frozen"):
        _assign(settings, "debug", True)
    method = "append"
    with pytest.raises(AttributeError):
        getattr(settings.cors.allow_origins, method)("*")


def test_s1_2_22_settings_are_loaded_once_per_process() -> None:
    get_settings.cache_clear()
    try:
        assert get_settings() is get_settings()
    finally:
        get_settings.cache_clear()
