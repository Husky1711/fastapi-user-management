"""Liveness and readiness probes for load balancers and Kubernetes.

- `/health/live`: the process is up. Never touches dependencies.
- `/health/ready`: the process can serve traffic. Checks every dependency in parallel with a
  timeout; returns 503 if any fails. Failure reasons are logged, never returned, because they
  can contain connection strings.
"""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.config import Settings
from app.core.logging import get_logger

HealthCheck = Callable[[], Awaitable[None]]
CheckResult = Literal["ok", "error", "timeout"]

router = APIRouter(prefix="/health", tags=["Health"])
log = get_logger(__name__)


class LivenessOut(BaseModel):
    status: Literal["alive"] = "alive"


class ReadinessOut(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, CheckResult]


async def _run_check(name: str, check: HealthCheck, limit_seconds: float) -> CheckResult:
    try:
        async with asyncio.timeout(limit_seconds):
            await check()
    except TimeoutError:
        log.warning("readiness check timed out", check=name, limit_seconds=limit_seconds)
        return "timeout"
    except Exception:
        log.exception("readiness check failed", check=name)
        return "error"
    return "ok"


async def run_checks(checks: Mapping[str, HealthCheck], limit_seconds: float) -> ReadinessOut:
    names = list(checks)
    results = await asyncio.gather(*(_run_check(n, checks[n], limit_seconds) for n in names))
    outcome = dict(zip(names, results, strict=True))
    ready = all(result == "ok" for result in results)
    return ReadinessOut(status="ready" if ready else "not_ready", checks=outcome)


@router.get("/live", response_model=LivenessOut)
async def live() -> LivenessOut:
    return LivenessOut()


@router.get(
    "/ready",
    response_model=ReadinessOut,
    responses={503: {"model": ReadinessOut, "description": "A dependency is unavailable"}},
)
async def ready(request: Request) -> JSONResponse:
    settings: Settings = request.app.state.settings
    checks: Mapping[str, HealthCheck] = request.app.state.health_checks
    result = await run_checks(checks, settings.health.check_timeout_seconds)
    status_code = 200 if result.status == "ready" else 503
    return JSONResponse(result.model_dump(), status_code=status_code)
