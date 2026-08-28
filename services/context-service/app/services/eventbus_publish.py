"""Publishes "context.collected" so investigation-service can auto-dispatch.

Reuses the same RedisStreamEventBus this service already connects for
consuming "incidents.created" (see eventbus_consumer.py) -- one connection,
one bus instance, used both to consume upstream events and publish
downstream ones.
"""

from __future__ import annotations

import uuid

import structlog

from app.config import get_settings
from app.services.eventbus_consumer import get_event_bus

logger = structlog.get_logger(__name__)


async def publish_context_collected(
    *, incident_id: uuid.UUID, severity: str, correlation_id: str
) -> None:
    settings = get_settings()
    bus = get_event_bus()
    entry_id = await bus.publish(
        settings.context_collected_stream,
        {
            "incident_id": str(incident_id),
            "severity": severity,
            "correlation_id": correlation_id,
        },
    )
    if entry_id is None:
        logger.warning(
            "context_collected_publish_failed",
            incident_id=str(incident_id),
        )
    else:
        logger.info(
            "context_collected_published",
            incident_id=str(incident_id),
            severity=severity,
            entry_id=entry_id,
        )
