"""Health, readiness, and liveness probes."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app import __version__
from app.config import get_settings
from app.faults import FaultType, fault_injector

router = APIRouter(tags=["health"])


@router.get("/healthz")
@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": __version__,
        "environment": settings.environment,
    }


@router.get("/livez")
@router.get("/health/live")
async def liveness() -> dict:
    """Process is alive. Always 200 unless the process is wedged."""
    settings = get_settings()
    return {"status": "healthy", "service": settings.service_name}


@router.get("/readyz")
@router.get("/health/ready")
async def readiness(response: Response) -> dict:
    """Ready to serve traffic. Memory-leak ballast can mark degraded."""
    settings = get_settings()
    memory_fault = fault_injector.is_active(FaultType.MEMORY_LEAK)
    if memory_fault:
        # Still ready in demo mode, but surface degraded state for operators
        response.status_code = status.HTTP_200_OK
        return {
            "status": "degraded",
            "service": settings.service_name,
            "detail": "memory_leak fault active",
        }
    return {"status": "healthy", "service": settings.service_name}
