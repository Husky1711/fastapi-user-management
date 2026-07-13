"""Contract tests for structured API error payloads (UI depends on error_code)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from utils.api_errors import APIHTTPException, error_payload, _STATUS_DEFAULT_CODES


REQUIRED_ERROR_KEYS = frozenset(
    {"detail", "error_code", "fields", "status_code", "correlation_id", "timestamp"}
)

# Stable codes the frontend / clients may branch on
KNOWN_EXPLICIT_CODES = frozenset(
    {
        "INVALID_CREDENTIALS",
        "ACCOUNT_LOCKED",
        "ACCOUNT_DISABLED",
        "INVALID_REFRESH_TOKEN",
        "INVALID_2FA_CODE",
        "2FA_ENROLLMENT_REQUIRED",
        "RATE_LIMIT_EXCEEDED",
        "REFRESH_REQUIRED",
        "FORBIDDEN",
        "STAFF_REQUIRED",
        "DASHBOARD_ROLE_REQUIRED",
        "PERMISSION_DENIED",
        "ORG_SETTINGS_DENIED",
        "INSUFFICIENT_PERMISSIONS",
        "BAD_REQUEST",
        "UNAUTHORIZED",
        "NOT_FOUND",
        "VALIDATION_ERROR",
        "INTERNAL_ERROR",
        "UNKNOWN_ERROR",
    }
)


@pytest.mark.parametrize(
    "status_code,expected_code",
    sorted(_STATUS_DEFAULT_CODES.items()),
)
def test_status_default_codes(status_code: int, expected_code: str) -> None:
    exc = APIHTTPException(status_code=status_code, detail="x")
    assert exc.error_code == expected_code
    assert expected_code in KNOWN_EXPLICIT_CODES or expected_code.endswith("_ERROR")


def test_api_http_exception_payload_shape() -> None:
    exc = APIHTTPException(
        status_code=401,
        detail="Could not validate credentials",
        error_code="INVALID_CREDENTIALS",
        fields={"username": "required"},
    )
    body = error_payload(exc, request_id="corr-1", timestamp=123.0)
    assert REQUIRED_ERROR_KEYS <= body.keys()
    assert body["error_code"] == "INVALID_CREDENTIALS"
    assert body["status_code"] == 401
    assert body["correlation_id"] == "corr-1"
    assert body["fields"] == {"username": "required"}
    assert body["detail"] == "Could not validate credentials"


def test_plain_http_exception_maps_credentials() -> None:
    exc = HTTPException(status_code=401, detail="Incorrect username or password")
    body = error_payload(exc, request_id="corr-2", timestamp=1.0)
    assert body["error_code"] == "INVALID_CREDENTIALS"
    assert REQUIRED_ERROR_KEYS <= body.keys()


def test_plain_http_exception_maps_refresh() -> None:
    exc = HTTPException(status_code=401, detail="Invalid refresh token")
    body = error_payload(exc, request_id="corr-3", timestamp=1.0)
    assert body["error_code"] == "INVALID_REFRESH_TOKEN"


def test_unhandled_exception_is_internal() -> None:
    body = error_payload(RuntimeError("boom"), request_id="corr-4", timestamp=1.0)
    assert body["error_code"] == "INTERNAL_ERROR"
    assert body["status_code"] == 500
    assert body["detail"] == "Internal server error"
    assert REQUIRED_ERROR_KEYS <= body.keys()


@pytest.mark.parametrize(
    "code",
    sorted(
        {
            "INVALID_CREDENTIALS",
            "ACCOUNT_LOCKED",
            "ACCOUNT_DISABLED",
            "INVALID_REFRESH_TOKEN",
            "INVALID_2FA_CODE",
            "2FA_ENROLLMENT_REQUIRED",
            "RATE_LIMIT_EXCEEDED",
            "REFRESH_REQUIRED",
            "STAFF_REQUIRED",
            "DASHBOARD_ROLE_REQUIRED",
            "PERMISSION_DENIED",
            "ORG_SETTINGS_DENIED",
        }
    ),
)
def test_explicit_api_codes_round_trip(code: str) -> None:
    exc = APIHTTPException(status_code=400, detail="test", error_code=code)
    body = error_payload(exc, request_id="c", timestamp=0.0)
    assert body["error_code"] == code
    assert code in KNOWN_EXPLICIT_CODES
