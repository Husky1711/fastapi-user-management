"""Unit tests for security logging attack detection and CSRF header."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from utils.cookie_auth import require_csrf_header
from utils.security_middleware import _looks_like_attack


def test_known_api_login_path_is_not_suspicious() -> None:
    assert not _looks_like_attack("/api/v1/login", "")
    assert not _looks_like_attack("/api/v1/dashboard/admin", "")
    assert not _looks_like_attack("/health", "")


def test_path_traversal_and_probes_are_suspicious() -> None:
    assert _looks_like_attack("/wp-admin", "")
    assert _looks_like_attack("/api/v1/users/../etc/passwd", "")
    assert _looks_like_attack("/unknown", "id=1 UNION SELECT password FROM users")


def test_require_csrf_header_rejects_missing() -> None:
    with pytest.raises(HTTPException) as exc:
        require_csrf_header(None)
    assert exc.value.status_code == 403


def test_require_csrf_header_accepts_xhr() -> None:
    require_csrf_header("XMLHttpRequest")


def test_db_startup_fail_open_never_in_production(monkeypatch) -> None:
    from main import _allow_db_startup_fail_open
    from config.settings import settings

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(settings.app, "environment", "production")
    assert _allow_db_startup_fail_open() is False

    monkeypatch.setattr(settings.app, "environment", "test")
    assert _allow_db_startup_fail_open() is True


def test_correlation_id_auto_injected_into_logs() -> None:
    from utils.logger import BaseLogger
    from utils.production_logging import CorrelationIDGenerator, get_request_context

    CorrelationIDGenerator.set("corr-test-123")
    logger = BaseLogger("corr_test")
    merged = logger._merge_request_context({})
    assert merged.get("correlation_id") == "corr-test-123"
    ctx = get_request_context()
    assert ctx is not None
    assert ctx.correlation_id == "corr-test-123"


def test_connect_args_include_mysql_timeout() -> None:
    from utils.database import _connect_args_for_url

    args = _connect_args_for_url("mysql+pymysql://u:p@localhost/db", 30)
    assert "MAX_EXECUTION_TIME=30000" in args.get("init_command", "")


@pytest.mark.integration
@pytest.mark.auth
def test_refresh_rejects_without_csrf_header(test_client_manager) -> None:
    client = test_client_manager.client
    login = client.post(
        "/api/v1/login",
        json={"username": "testuser", "password": "user123"},
    )
    assert login.status_code == 200
    refresh_token = login.json()["refresh_token"]

    denied = client.post(
        "/api/v1/refresh",
        json={"refresh_token": refresh_token},
    )
    assert denied.status_code == 403
