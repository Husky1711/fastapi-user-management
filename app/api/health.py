"""Liveness and readiness probes for load balancers and Kubernetes.

- `/health/live`: the process is up. Never touches dependencies.
- `/health/ready`: the process can serve traffic (see `app/services/health.py`); 503 if not.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.schemas.errors import COMMON_ERROR_RESPONSES
from app.schemas.health import LivenessOut, ReadinessOut
from app.services.health import ReadinessProbe

router = APIRouter(prefix="/health", tags=["Health"], responses=COMMON_ERROR_RESPONSES)


def get_readiness_probe(request: Request) -> ReadinessProbe:
    probe: ReadinessProbe = request.app.state.readiness
    return probe


@router.get("/live")
async def live() -> LivenessOut:
    return LivenessOut()


@router.get(
    "/ready",
    responses={503: {"model": ReadinessOut, "description": "A dependency is unavailable"}},
)
async def ready(
    response: Response, probe: Annotated[ReadinessProbe, Depends(get_readiness_probe)]
) -> ReadinessOut:
    result = await probe.run()
    if result.status != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
