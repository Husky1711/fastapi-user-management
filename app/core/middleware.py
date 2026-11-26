"""The single HTTP middleware (pure ASGI, no BaseHTTPMiddleware overhead).

For every HTTP request it:
- assigns a request id (reuses a well-formed incoming `X-Request-ID`, else generates one),
  exposes it to logs and error bodies, and returns it in the response header;
- adds security headers;
- logs exactly one line with method, path, status and duration;
- turns any unhandled exception into a generic RFC 9457 500 response.
"""

import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import internal_error_response
from app.core.logging import get_logger, request_id_var

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}
HSTS_HEADER = ("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
# JSON responses never need to load scripts, styles or frames. The interactive docs pages
# (development only) load Swagger UI from a CDN, so they are exempt.
API_CSP_HEADER = ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
DOCS_PATHS = frozenset({"/docs", "/docs/oauth2-redirect", "/redoc"})

log = get_logger(__name__)


def _incoming_request_id(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name.decode("latin-1").lower() == REQUEST_ID_HEADER.lower():
            candidate = value.decode("latin-1")
            return candidate if _VALID_REQUEST_ID.fullmatch(candidate) else None
    return None


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp, *, enable_hsts: bool = False) -> None:
        self.app = app
        self.enable_hsts = enable_hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope) or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_headers(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
                for name, value in SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
                if self.enable_hsts:
                    headers.setdefault(*HSTS_HEADER)
                if scope["path"] not in DOCS_PATHS:
                    headers.setdefault(*API_CSP_HEADER)
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except Exception:
            log.exception("unhandled exception", path=scope["path"])
            if response_started:
                raise
            await internal_error_response()(scope, receive, send_with_headers)
        finally:
            log.info(
                "request",
                method=scope["method"],
                path=scope["path"],
                status=status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                client_ip=scope["client"][0] if scope.get("client") else None,
            )
            request_id_var.reset(token)
