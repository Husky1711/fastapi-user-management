"""Liveness and readiness probes for load balancers and Kubernetes.

- `/health/live`: the process is up. Never touches dependencies.
- `/health/ready`: the process can serve traffic (see `app/services/health.py`); 503 if not.
"""

from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.health import ReadinessOut, ReadinessProbe

router = APIRouter(prefix="/health", tags=["Health"])


class LivenessOut(BaseModel):
    status: Literal["alive"] = "alive"


@router.get("/live", response_model=LivenessOut)
async def live() -> LivenessOut:
    return LivenessOut()


@router.get(
    "/ready",
    response_model=ReadinessOut,
    responses={503: {"model": ReadinessOut, "description": "A dependency is unavailable"}},
)
async def ready(request: Request) -> JSONResponse:
    probe: ReadinessProbe = request.app.state.readiness
    result = await probe.run()
    status_code = 200 if result.status == "ready" else 503
    return JSONResponse(result.model_dump(), status_code=status_code)
