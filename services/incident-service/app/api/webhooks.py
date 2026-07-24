"""Alertmanager webhook ingestion endpoint."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.alertmanager import AlertmanagerWebhook
from app.schemas.incident import WebhookIngestResponse
from app.services import incident_service
from app.services.context_client import trigger_context_collection

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


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

    # Phase 3: automatically gather investigation context for newly created incidents
    for item in result.results:
        if item.action == "created":
            background_tasks.add_task(trigger_context_collection, item.incident_id)
            logger.info(
                "context_collection_scheduled",
                incident_id=str(item.incident_id),
            )

    return result
