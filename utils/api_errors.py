#!/usr/bin/env python3
"""Structured API errors with machine-readable error codes."""

from typing import Any, Dict, Optional

from fastapi import HTTPException


# Default codes when callers omit error_code
_STATUS_DEFAULT_CODES: Dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    422: "VALIDATION_ERROR",
    423: "ACCOUNT_LOCKED",
    429: "RATE_LIMIT_EXCEEDED",
    500: "INTERNAL_ERROR",
}


class APIHTTPException(HTTPException):
    """HTTPException that carries a stable error_code for the UI."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        fields: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code or _STATUS_DEFAULT_CODES.get(
            status_code, "UNKNOWN_ERROR"
        )
        self.fields = fields or {}


def error_payload(
    exc: Exception,
    request_id: str,
    timestamp: float,
) -> Dict[str, Any]:
    """Build a consistent JSON error body."""
    if isinstance(exc, APIHTTPException):
        return {
            "detail": exc.detail,
            "error_code": exc.error_code,
            "fields": exc.fields,
            "status_code": exc.status_code,
            "correlation_id": request_id,
            "timestamp": timestamp,
        }

    if isinstance(exc, HTTPException):
        code = _STATUS_DEFAULT_CODES.get(exc.status_code, "UNKNOWN_ERROR")
        detail = exc.detail
        fields: Dict[str, Any] = {}

        if exc.status_code == 401 and isinstance(detail, str):
            if "Incorrect username" in detail or "credentials" in detail.lower():
                code = "INVALID_CREDENTIALS"
            elif "refresh" in detail.lower():
                code = "INVALID_REFRESH_TOKEN"
        elif exc.status_code == 423:
            code = "ACCOUNT_LOCKED"
        elif exc.status_code == 429:
            code = "RATE_LIMIT_EXCEEDED"

        return {
            "detail": detail,
            "error_code": code,
            "fields": fields,
            "status_code": exc.status_code,
            "correlation_id": request_id,
            "timestamp": timestamp,
        }

    return {
        "detail": "Internal server error",
        "error_code": "INTERNAL_ERROR",
        "fields": {},
        "status_code": 500,
        "correlation_id": request_id,
        "timestamp": timestamp,
    }
