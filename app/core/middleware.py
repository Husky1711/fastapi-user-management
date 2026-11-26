"""HTTP middleware (pure ASGI, no BaseHTTPMiddleware overhead).

`RequestContextMiddleware` is the outermost layer. For every HTTP request it:
- assigns a request id (reuses a well-formed incoming `X-Request-ID`, else generates one),
  exposes it to logs and error bodies, and returns it in the response header;
- adds security headers;
- logs exactly one line with method, path, status, duration, client IP and user agent.

`ErrorBoundaryMiddleware` is the innermost layer. It turns any unhandled exception into a
generic RFC 9457 500, *inside* CORS, so browser clients can read the error and its request id.
A client that disconnects is not an error: nothing is sent and the request is logged as 499.
"""

import asyncio
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.requests import ClientDisconnect
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import internal_error_response
from app.core.logging import get_logger, request_id_var

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_HEADER_BYTES = REQUEST_ID_HEADER.lower().encode("latin-1")
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
MAX_LOGGED_USER_AGENT = 256
CLIENT_CLOSED_REQUEST = 499  # de-facto status for "client went away" (nginx convention)

SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}
HSTS_HEADER = ("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
# JSON responses never need to load scripts, styles or frames. The interactive docs pages
# (development and test only) load Swagger UI from a CDN, so they are exempt.
API_CSP_HEADER = ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
DOCS_PATHS = frozenset({"/docs", "/docs/oauth2-redirect", "/redoc"})

log = get_logger(__name__)


def _header(scope: Scope, name: bytes) -> str | None:
    """First value of a request header, or None."""
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return bytes(value).decode("latin-1")
    return None


def _incoming_request_id(scope: Scope) -> str | None:
    candidate = _header(scope, _REQUEST_ID_HEADER_BYTES)
    if candidate is not None and _VALID_REQUEST_ID.fullmatch(candidate):
        return candidate
    return None


class ErrorBoundaryMiddleware:
    """Innermost layer: unhandled exception → generic 500 (no internal details)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        response_started = False

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except ClientDisconnect:
            # The client went away while we read its request: nobody to answer. The access
            # log records 499 because no response was sent.
            return
        except Exception:
            log.exception("unhandled exception", path=scope["path"])
            if response_started:
                raise  # too late for a clean error response; let the server close it
            await internal_error_response()(scope, receive, send)


class RequestContextMiddleware:
    """Outermost layer: request id, security headers, one access-log line per request."""

    def __init__(self, app: ASGIApp, *, enable_hsts: bool = False) -> None:
        self.app = app
        self.enable_hsts = enable_hsts

    def _add_headers(self, message: Message, scope: Scope, request_id: str) -> None:
        headers = MutableHeaders(scope=message)
        headers[REQUEST_ID_HEADER] = request_id
        for name, value in SECURITY_HEADERS.items():
            headers.setdefault(name, value)
        if self.enable_hsts:
            headers.setdefault(*HSTS_HEADER)
        if scope["path"] not in DOCS_PATHS:
            headers.setdefault(*API_CSP_HEADER)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope) or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        # Stays 499 only if the app finished without sending any response (client went away).
        status_code = CLIENT_CLOSED_REQUEST
        response_started = False

        async def send_with_headers(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                self._add_headers(message, scope, request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except asyncio.CancelledError:
            # The request was cancelled (e.g. server shutdown): not a server error. status_code
            # stays 499 unless a response had already started.
            raise
        except Exception:
            if response_started:
                # The error boundary (or the server) logs this; logging here would duplicate it.
                raise
            # Last resort for failures outside the error boundary (e.g. in other middleware).
            log.exception("unhandled exception", path=scope["path"])
            await internal_error_response()(scope, receive, send_with_headers)
        finally:
            log.info(
                "request",
                method=scope["method"],
                path=scope["path"],
                status=status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                client_ip=scope["client"][0] if scope.get("client") else None,
                user_agent=(_header(scope, b"user-agent") or "")[:MAX_LOGGED_USER_AGENT] or None,
            )
            request_id_var.reset(token)
