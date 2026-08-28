"""Background consumer: durable "incident created" dispatch via Redis Streams.

Runs as a long-lived asyncio task started in main.py's lifespan. Each event
calls the exact same orchestrator.collect_for_incident() the HTTP
POST /incidents/{id}/collect route calls -- this is a second entry point
into the same logic, not a parallel implementation, so there is nothing new
to keep in sync when collection behavior changes.

Only entries this service successfully processes are acked. A transient
failure (e.g. Prometheus/Loki momentarily unreachable) leaves the entry
pending, so it's redelivered on the next consume() call instead of being
silently lost -- this is the actual property the event bus buys over the
fire-and-forget HTTP call it replaced. A permanent failure (incident not
found upstream) is acked anyway; retrying it forever would never succeed.
"""

from __future__ import annotations

import asyncio
import uuid

import structlog

from app.config import get_settings
from app.db.session import get_session_factory

try:
    from libs.common.eventbus import RedisStreamEventBus
except ImportError:  # pragma: no cover
    from common.eventbus import RedisStreamEventBus  # type: ignore

logger = structlog.get_logger(__name__)

_bus: RedisStreamEventBus | None = None
_consumer_name = f"context-service-{uuid.uuid4().hex[:8]}"


def get_event_bus() -> RedisStreamEventBus:
    global _bus
    if _bus is None:
        settings = get_settings()
        _bus = RedisStreamEventBus(settings.redis_url, enabled=settings.event_bus_enabled)
    return _bus


async def _process_one(entry_id: str, fields: dict) -> bool:
    """Returns True if the entry should be acked (processed, or permanently
    unprocessable), False if it should be left pending for redelivery."""
    from app.services.orchestrator import IncidentLookupError, collect_for_incident

    raw_id = fields.get("incident_id")
    if not raw_id:
        logger.warning("eventbus_entry_missing_incident_id", entry_id=entry_id, fields=fields)
        return True  # malformed entry; nothing to retry towards

    try:
        incident_id = uuid.UUID(str(raw_id))
    except ValueError:
        logger.warning("eventbus_entry_bad_incident_id", entry_id=entry_id, raw_id=raw_id)
        return True

    factory = get_session_factory()
    async with factory() as session:
        try:
            ctx = await collect_for_incident(session, incident_id)
            await session.commit()
            logger.info(
                "eventbus_context_collected",
                incident_id=str(incident_id),
                context_id=str(ctx.id),
                entry_id=entry_id,
            )
            return True
        except IncidentLookupError as exc:
            # incident-service doesn't have this incident (or is down) --
            # this won't resolve itself by redelivery, so ack and move on.
            await session.rollback()
            logger.warning(
                "eventbus_incident_lookup_failed",
                incident_id=str(incident_id),
                entry_id=entry_id,
                error=str(exc),
            )
            return True
        except Exception as exc:  # noqa: BLE001
            # Transient (Prometheus/Loki/DB blip): leave unacked, retry later.
            await session.rollback()
            logger.warning(
                "eventbus_collect_failed_will_retry",
                incident_id=str(incident_id),
                entry_id=entry_id,
                error=str(exc),
            )
            return False


async def run_consumer_loop(stop_event: asyncio.Event) -> None:
    settings = get_settings()
    bus = get_event_bus()
    await bus.connect()
    if not bus.available:
        logger.warning("eventbus_consumer_disabled_no_redis")
        return

    await bus.ensure_group(settings.incidents_stream, settings.incidents_consumer_group)
    logger.info(
        "eventbus_consumer_started",
        stream=settings.incidents_stream,
        group=settings.incidents_consumer_group,
        consumer=_consumer_name,
    )

    while not stop_event.is_set():
        entries = await bus.consume(
            settings.incidents_stream,
            settings.incidents_consumer_group,
            _consumer_name,
            block_ms=3000,
        )
        for entry_id, fields in entries:
            ok = await _process_one(entry_id, fields)
            if ok:
                await bus.ack(
                    settings.incidents_stream, settings.incidents_consumer_group, entry_id
                )
        if not entries:
            await asyncio.sleep(0.1)  # yield between empty polls

    await bus.close()
    logger.info("eventbus_consumer_stopped")
