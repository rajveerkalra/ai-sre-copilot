"""Incident + investigation HTTP clients."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)


class UpstreamError(Exception):
    pass


def _service_headers() -> dict[str, str]:
    settings = get_settings()
    headers: dict[str, str] = {}
    if settings.internal_service_token:
        headers["X-Service-Token"] = settings.internal_service_token
    return headers


async def fetch_latest_investigation(incident_id: uuid.UUID) -> dict[str, Any]:
    settings = get_settings()
    url = f"{settings.investigation_service_url.rstrip('/')}/incidents/{incident_id}/investigation"
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        resp = await client.get(url, headers=_service_headers())
        if resp.status_code == 404:
            raise UpstreamError("No investigation for incident")
        if resp.status_code >= 400:
            raise UpstreamError(f"investigation-service {resp.status_code}: {resp.text[:200]}")
        return resp.json()


async def fetch_rca(investigation_id: uuid.UUID) -> dict[str, Any]:
    settings = get_settings()
    url = f"{settings.investigation_service_url.rstrip('/')}/investigations/{investigation_id}/rca"
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        resp = await client.get(url, headers=_service_headers())
        if resp.status_code == 404:
            raise UpstreamError("RCA not available")
        if resp.status_code >= 400:
            raise UpstreamError(f"investigation-service {resp.status_code}: {resp.text[:200]}")
        return resp.json()


async def post_timeline_event(
    incident_id: uuid.UUID,
    *,
    event_type: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    settings = get_settings()
    url = f"{settings.incident_service_url.rstrip('/')}/incidents/{incident_id}/timeline-events"
    payload = {
        "event_type": event_type,
        "message": message,
        "metadata": metadata or {},
    }
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.post(url, json=payload, headers=_service_headers())
            if resp.status_code >= 400:
                logger.warning(
                    "timeline_event_failed",
                    status=resp.status_code,
                    detail=resp.text[:200],
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("timeline_event_error", error=str(exc))
