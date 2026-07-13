#!/usr/bin/env python3
"""httpOnly refresh-token cookie helpers for browser clients."""

from utils.datetime_utc import utc_now
from typing import Any, Dict, Optional

from fastapi import Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from config.settings import settings

# Custom header required on cookie-auth mutating endpoints (refresh/logout).
# Browsers do not attach this on simple cross-site form POSTs, blocking CSRF.
CSRF_HEADER_NAME = "X-Requested-With"
CSRF_HEADER_VALUE = "XMLHttpRequest"


def require_csrf_header(
    x_requested_with: Optional[str] = Header(None, alias=CSRF_HEADER_NAME),
) -> None:
    """Reject requests without the SPA CSRF custom header."""
    if not x_requested_with or x_requested_with.strip() != CSRF_HEADER_VALUE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing or invalid {CSRF_HEADER_NAME} header",
        )


def get_refresh_token_from_request(request: Request) -> Optional[str]:
    """Read refresh token from the httpOnly cookie."""
    return request.cookies.get(settings.auth_cookie.name)


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Attach httpOnly refresh cookie to a response."""
    if not settings.auth_cookie.use_httponly_refresh:
        return

    max_age = settings.jwt.refresh_token_expire_days * 24 * 60 * 60
    cookie_kwargs: Dict[str, Any] = {
        "key": settings.auth_cookie.name,
        "value": refresh_token,
        "max_age": max_age,
        "httponly": True,
        "secure": settings.auth_cookie.secure,
        "samesite": settings.auth_cookie.samesite,
        "path": settings.auth_cookie.path,
    }
    if settings.auth_cookie.domain:
        cookie_kwargs["domain"] = settings.auth_cookie.domain

    response.set_cookie(**cookie_kwargs)


def clear_refresh_cookie(response: Response) -> None:
    """Remove refresh cookie from the client."""
    delete_kwargs: Dict[str, Any] = {
        "key": settings.auth_cookie.name,
        "path": settings.auth_cookie.path,
        "httponly": True,
        "secure": settings.auth_cookie.secure,
        "samesite": settings.auth_cookie.samesite,
    }
    if settings.auth_cookie.domain:
        delete_kwargs["domain"] = settings.auth_cookie.domain

    response.delete_cookie(**delete_kwargs)


def resolve_refresh_token(
    request: Request, body_token: Optional[str]
) -> Optional[str]:
    """
    Resolve refresh token for refresh/logout.

    When legacy JSON is enabled and the client sends a body token, prefer the body
    so API/TestClient callers are not overridden by a stale httpOnly cookie after
    rotation. Cookie-only browser clients (no body) still use the cookie.
    """
    if settings.auth_cookie.legacy_json_refresh and body_token:
        return body_token
    cookie_token = get_refresh_token_from_request(request)
    if cookie_token:
        return cookie_token
    return body_token


def build_auth_token_response(
    access_token: str,
    refresh_token: str,
    expires_in: Optional[int] = None,
    session_info: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    """
    Return access token in JSON and refresh token in httpOnly cookie.
    During transition, refresh_token may also appear in the JSON body.
    """
    if expires_in is None:
        expires_in = settings.jwt.access_token_expire_minutes * 60

    body: Dict[str, Any] = {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
    }
    if settings.auth_cookie.legacy_json_refresh:
        body["refresh_token"] = refresh_token
    if session_info is not None:
        body["session_info"] = session_info

    response = JSONResponse(content=body)
    set_refresh_cookie(response, refresh_token)
    return response


def build_logout_response(message: str = "Successfully logged out") -> JSONResponse:
    """Logout JSON body with refresh cookie cleared."""
    response = JSONResponse(
        content={
            "message": message,
            "timestamp": utc_now().isoformat(),
        }
    )
    clear_refresh_cookie(response)
    return response
