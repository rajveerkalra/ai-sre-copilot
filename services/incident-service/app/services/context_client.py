"""Fire-and-forget trigger for Phase 3 context collection."""

from __future__ import annotations

import uuid

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)


async def trigger_context_collection(incident_id: uuid.UUID) -> None:
    """POST to context-service; failures are logged and never raised."""
    settings = get_settings()
    if not settings.context_service_enabled:
        logger.info(
            "context_collection_skipped",
            incident_id=str(incident_id),
            reason="disabled",
        )
        return

    url = (
        f"{settings.context_service_url.rstrip('/')}"
        f"/incidents/{incident_id}/collect"
    )
    try:
        async with httpx.AsyncClient(timeout=settings.context_service_timeout_seconds) as client:
            resp = await client.post(url, json={"force": False})
            if resp.status_code >= 400:
                logger.warning(
                    "context_collection_trigger_failed",
                    incident_id=str(incident_id),
                    status_code=resp.status_code,
                    body=resp.text[:500],
                )
            else:
                logger.info(
                    "context_collection_triggered",
                    incident_id=str(incident_id),
                    status_code=resp.status_code,
                    response=resp.json() if resp.headers.get("content-type", "").startswith("application/json") else None,
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "context_collection_trigger_error",
            incident_id=str(incident_id),
            error=str(exc),
        )
