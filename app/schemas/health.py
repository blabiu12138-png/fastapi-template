from typing import Literal

from pydantic import BaseModel

type DependencyStatus = Literal["disabled", "ok", "error"]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessChecks(BaseModel):
    database: DependencyStatus
    redis: DependencyStatus


class ReadinessResponse(BaseModel):
    status: Literal["ok", "error"]
    checks: ReadinessChecks
