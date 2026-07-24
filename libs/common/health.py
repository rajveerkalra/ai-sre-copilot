"""Health / readiness / liveness response models shared across services."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class CheckResult(BaseModel):
    name: str
    status: HealthStatus
    detail: str | None = None
    latency_ms: float | None = None


class HealthResponse(BaseModel):
    status: HealthStatus
    service: str
    version: str
    checks: list[CheckResult] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class ProbeResponse(BaseModel):
    status: HealthStatus
    service: str
