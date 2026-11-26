"""Readiness checking: can this instance serve traffic?

Checks run in parallel, each under a time limit. A probe with no checks is never ready.
Failures are logged as the exception type plus a redacted, shortened message (credentials in
URLs removed, no traceback) and are never returned to the caller.

Rate-limit policy: probes are exempt from per-client rate limits (load balancers call them
constantly). Instead, results are cached for `cache_seconds` and refreshed by one caller at a
time (single flight), so a flood of probes costs at most one database and one Redis round trip
per window.
"""

import asyncio
import re
import time
from collections.abc import Awaitable, Callable, Mapping

from app.core.logging import get_logger
from app.schemas.health import CheckResult, ReadinessOut

HealthCheck = Callable[[], Awaitable[None]]

# "scheme://user:password@host" → "scheme://***@host"
_URL_CREDENTIALS = re.compile(r"([a-z][a-z0-9+.-]*://)[^@/\s]+@", re.IGNORECASE)
MAX_LOGGED_ERROR = 200

log = get_logger(__name__)


def redact(message: str) -> str:
    """Remove credentials embedded in URLs and cap the length, for logging."""
    return _URL_CREDENTIALS.sub(r"\1***@", message)[:MAX_LOGGED_ERROR]


async def _run_check(name: str, check: HealthCheck, limit_seconds: float) -> CheckResult:
    try:
        async with asyncio.timeout(limit_seconds):
            await check()
    except TimeoutError:
        log.warning("readiness check timed out", check=name, limit_seconds=limit_seconds)
        return "timeout"
    except Exception as exc:
        log.warning(
            "readiness check failed",
            check=name,
            error_type=type(exc).__name__,
            error=redact(str(exc)),
        )
        return "error"
    return "ok"


async def run_checks(checks: Mapping[str, HealthCheck], limit_seconds: float) -> ReadinessOut:
    names = list(checks)
    results = await asyncio.gather(*(_run_check(n, checks[n], limit_seconds) for n in names))
    # No checks means nothing was verified: never report ready (fail closed).
    ready = bool(results) and all(result == "ok" for result in results)
    return ReadinessOut(
        status="ready" if ready else "not_ready",
        checks=dict(zip(names, results, strict=True)),
    )


class ReadinessProbe:
    def __init__(
        self,
        checks: Mapping[str, HealthCheck],
        *,
        limit_seconds: float,
        cache_seconds: float,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._checks = dict(checks)
        self._limit_seconds = limit_seconds
        self._cache_seconds = cache_seconds
        self._monotonic = monotonic
        self._lock = asyncio.Lock()
        self._result: ReadinessOut | None = None
        self._checked_at = 0.0

    @property
    def check_names(self) -> tuple[str, ...]:
        return tuple(self._checks)

    def _fresh(self) -> ReadinessOut | None:
        if self._result is None or self._cache_seconds == 0:
            return None
        if self._monotonic() - self._checked_at >= self._cache_seconds:
            return None
        return self._result

    async def run(self) -> ReadinessOut:
        cached = self._fresh()
        if cached is not None:
            return cached
        async with self._lock:
            cached = self._fresh()  # another caller may have refreshed while we waited
            if cached is not None:
                return cached
            self._result = await run_checks(self._checks, self._limit_seconds)
            self._checked_at = self._monotonic()
            return self._result
