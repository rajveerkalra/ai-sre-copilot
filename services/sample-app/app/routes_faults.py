"""Fault injection control plane for demo scenarios."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.faults import FaultType, fault_injector

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/faults", tags=["faults"])


class FaultActivateRequest(BaseModel):
    duration_seconds: float | None = Field(
        default=120,
        ge=1,
        le=3600,
        description="Auto-expire after N seconds; omit/null for until deactivated",
    )
    error_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    min_ms: float | None = Field(default=None, ge=0)
    max_ms: float | None = Field(default=None, ge=0)
    workers: int | None = Field(default=None, ge=1, le=8)
    megabytes: int | None = Field(default=None, ge=1, le=1024)
    hard: bool | None = Field(
        default=None,
        description="For crash fault: hard=true calls os._exit(1)",
    )


@router.get("")
@router.get("/")
async def list_faults() -> dict[str, Any]:
    return {
        "faults": fault_injector.status(),
        "available": [ft.value for ft in FaultType],
        "scenarios": {
            "high_error_rate": {
                "fault": "error_storm",
                "params": {"error_rate": 0.9, "duration_seconds": 180},
            },
            "high_latency": {
                "fault": "latency",
                "params": {"min_ms": 800, "max_ms": 2500, "duration_seconds": 180},
            },
            "high_cpu": {
                "fault": "cpu_spike",
                "params": {"workers": 2, "duration_seconds": 120},
            },
            "high_memory": {
                "fault": "memory_leak",
                "params": {"megabytes": 256, "duration_seconds": 180},
            },
            "dependency_timeout": {
                "fault": "dependency_timeout",
                "params": {"duration_seconds": 180},
            },
        },
    }


@router.post("/{fault_type}/activate")
async def activate_fault(
    fault_type: str, body: FaultActivateRequest | None = None
) -> dict[str, Any]:
    body = body or FaultActivateRequest()
    try:
        ft = FaultType(fault_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown fault type '{fault_type}'. "
            f"Available: {[f.value for f in FaultType]}",
        ) from exc

    params: dict[str, Any] = {}
    if body.error_rate is not None:
        params["error_rate"] = body.error_rate
    if body.min_ms is not None:
        params["min_ms"] = body.min_ms
    if body.max_ms is not None:
        params["max_ms"] = body.max_ms
    if body.workers is not None:
        params["workers"] = body.workers
    if body.megabytes is not None:
        params["megabytes"] = body.megabytes
    if body.hard is not None:
        params["hard"] = body.hard

    # Sensible defaults per fault
    if ft == FaultType.ERROR_STORM and "error_rate" not in params:
        params["error_rate"] = 0.85
    if ft == FaultType.LATENCY:
        params.setdefault("min_ms", 500)
        params.setdefault("max_ms", 2000)
    if ft == FaultType.CPU_SPIKE:
        params.setdefault("workers", 2)
    if ft == FaultType.MEMORY_LEAK:
        params.setdefault("megabytes", 128)

    try:
        state = fault_injector.activate(
            ft, duration_seconds=body.duration_seconds, **params
        )
    except RuntimeError as exc:
        # Soft crash — return 500 as the "crash"
        logger.error("crash_fault_injected", hard=False)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.warning(
        "fault_activated",
        fault_type=ft.value,
        params=params,
        duration_seconds=body.duration_seconds,
    )
    return {"fault": ft.value, "state": state}


@router.post("/{fault_type}/deactivate")
async def deactivate_fault(fault_type: str) -> dict[str, Any]:
    try:
        ft = FaultType(fault_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Unknown fault type") from exc

    state = fault_injector.deactivate(ft)
    logger.info("fault_deactivated", fault_type=ft.value)
    return {"fault": ft.value, "state": state}


@router.post("/deactivate-all")
async def deactivate_all() -> dict[str, Any]:
    state = fault_injector.deactivate_all()
    logger.info("all_faults_deactivated")
    return {"faults": state}
