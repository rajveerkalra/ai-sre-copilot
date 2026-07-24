"""Health probes."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app import __version__
from app.config import get_settings
from app.db.session import check_db

router = APIRouter(tags=["health"])


@router.get("/health")
@router.get("/healthz")
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": __version__,
    }


@router.get("/live")
@router.get("/livez")
async def live() -> dict:
    return {"status": "healthy", "service": get_settings().service_name}


@router.get("/ready")
@router.get("/readyz")
async def ready(response: Response) -> dict:
    settings = get_settings()
    try:
        await check_db()
        return {"status": "healthy", "service": settings.service_name, "db": "ok"}
    except Exception as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "service": settings.service_name,
            "db": "error",
            "detail": str(exc),
        }
