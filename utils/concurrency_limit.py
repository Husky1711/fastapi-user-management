"""Bound in-flight requests per process so the DB pool can never deadlock.

Why: endpoints and dependencies are sync and run in AnyIO's threadpool, one hop per
dependency. A request checks out its DB connection in its first DB-using dependency
and holds it until the response is done. If more requests are in flight than the
pool has connections, every worker thread can end up waiting on the pool while the
connections are held by requests waiting for a thread — nothing progresses until
``pool_timeout`` (observed under load: 30 s hangs).

Admitting at most ``pool_size + max_overflow - reserve`` requests at a time removes
that cycle. Excess requests wait here, before any dependency runs, holding nothing;
after ``queue_timeout`` seconds they get a 503 with Retry-After.
"""

from __future__ import annotations

import asyncio
import json
from typing import Iterable

from starlette.types import ASGIApp, Receive, Scope, Send

_BYPASS_DEFAULT = ("/health/live", "/health", "/metrics")


class ConcurrencyLimitMiddleware:
    """Pure ASGI middleware (no BaseHTTPMiddleware overhead)."""

    def __init__(
        self,
        app: ASGIApp,
        max_concurrent: int,
        queue_timeout: float,
        bypass_paths: Iterable[str] = _BYPASS_DEFAULT,
    ) -> None:
        self.app = app
        self.max_concurrent = max(1, int(max_concurrent))
        self.queue_timeout = float(queue_timeout)
        self.bypass_paths = frozenset(bypass_paths)
        self._slots: asyncio.Semaphore | None = None  # created on the serving loop

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in self.bypass_paths:
            await self.app(scope, receive, send)
            return
        if self._slots is None:
            self._slots = asyncio.Semaphore(self.max_concurrent)
        try:
            await asyncio.wait_for(self._slots.acquire(), timeout=self.queue_timeout)
        except asyncio.TimeoutError:
            await _send_busy(send, retry_after=max(1, int(self.queue_timeout)))
            return
        try:
            await self.app(scope, receive, send)
        finally:
            self._slots.release()


async def _send_busy(send: Send, retry_after: int) -> None:
    body = json.dumps(
        {
            "detail": "Server is busy, please retry shortly",
            "error_code": "SERVICE_UNAVAILABLE",
            "status_code": 503,
        }
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 503,
            "headers": [
                (b"content-type", b"application/json"),
                (b"retry-after", str(retry_after).encode()),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
