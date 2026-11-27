"""Response schemas for the health probes."""

from typing import Literal

from pydantic import BaseModel

CheckResult = Literal["ok", "error", "timeout"]


class LivenessOut(BaseModel):
    status: Literal["alive"] = "alive"


class ReadinessOut(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, CheckResult]
