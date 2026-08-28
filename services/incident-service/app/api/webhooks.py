"""Alertmanager webhook ingestion endpoint."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.schemas.alertmanager import AlertmanagerWebhook
from app.schemas.incident import WebhookIngestResponse
from app.services import incident_service
from app.services.context_client import trigger_context_collection
from app.services.eventbus_client import get_event_bus

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _dispatch_context_collection(incident_id, alertname: str, background_tasks: BackgroundTasks) -> None:
    """Durable dispatch via the event bus, falling back to the old
    fire-and-forget HTTP call only if the bus itself is unreachable -- so a
    Redis blip never means an incident silently gets no investigation."""
    settings = get_settings()
    bus = get_event_bus()
    entry_id = await bus.publish(
        settings.incidents_stream,
        {"incident_id": str(incident_id), "alertname": alertname},
    )
    if entry_id is not None:
        logger.info(
            "context_collection_published",
            incident_id=str(incident_id),
            stream=settings.incidents_stream,
            entry_id=entry_id,
        )
        return

    logger.warning(
        "event_bus_unavailable_falling_back_to_direct_http",
        incident_id=str(incident_id),
    )
    background_tasks.add_task(trigger_context_collection, incident_id)


@router.post("/alertmanager", response_model=WebhookIngestResponse)
async def alertmanager_webhook(
    payload: AlertmanagerWebhook,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> WebhookIngestResponse:
    logger.info(
        "alertmanager_webhook_received",
        status=payload.status,
        alert_count=len(payload.alerts),
        receiver=payload.receiver,
    )
    result = await incident_service.ingest_alertmanager_webhook(db, payload)

    # Automatically gather investigation context for newly created incidents,
    # dispatched durably via the event bus (see _dispatch_context_collection).
    for item in result.results:
        if item.action == "created":
            await _dispatch_context_collection(item.incident_id, item.alertname, background_tasks)

    return result
