"""Auto-dispatch: context.collected -> priority queue -> bounded worker pool.

Two independent asyncio tasks, both started in main.py's lifespan:

1. `run_dispatch_consumer` -- durable ingest. Reads "context.collected" from
   Redis Streams via a consumer group (so it survives this service being
   briefly down) and enqueues each incident into a Redis-backed priority
   queue keyed by severity, then acks the stream entry. Enqueueing is
   effectively instant, so this can absorb an arbitrarily large burst of
   incidents without blocking on investigation itself.

2. `run_investigation_worker` (one instance per worker slot, N =
   settings.max_concurrent_investigations) -- drains the priority queue at a
   fixed, bounded concurrency. This is the actual throughput control: no
   matter how many incidents are queued, only N investigations ever run at
   once, and the lowest-priority-score (highest severity) item always goes
   next. See config.py for why N is a hard ceiling, not a suggestion --
   LLM investigation is compute-bound, and workers beyond what the model
   backend can serve concurrently just queue behind each other anyway.

Both are best-effort against Redis: if it's unavailable, dispatch simply
doesn't happen and incidents fall back to being investigated only via a
manual POST /incidents/{id}/investigate call, same as before this existed.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid

import structlog

from app.config import get_settings
from app.db.session import get_session_factory
from app.metrics import INVESTIGATION_QUEUE_DEPTH, INVESTIGATIONS_DEQUEUED_TOTAL

try:
    from libs.common.eventbus import RedisPriorityQueue, RedisStreamEventBus
except ImportError:  # pragma: no cover
    from common.eventbus import RedisPriorityQueue, RedisStreamEventBus  # type: ignore

logger = structlog.get_logger(__name__)

_bus: RedisStreamEventBus | None = None
_queue: RedisPriorityQueue | None = None
_consumer_name = f"investigation-service-{uuid.uuid4().hex[:8]}"


def get_event_bus() -> RedisStreamEventBus:
    global _bus
    if _bus is None:
        settings = get_settings()
        _bus = RedisStreamEventBus(settings.redis_url, enabled=settings.event_bus_enabled)
    return _bus


def get_priority_queue() -> RedisPriorityQueue:
    global _queue
    if _queue is None:
        settings = get_settings()
        _queue = RedisPriorityQueue(settings.redis_url, enabled=settings.event_bus_enabled)
    return _queue


def priority_score(severity: str) -> float:
    """Lower score = drained sooner. Same-severity items still drain
    oldest-first, since the timestamp component dominates within a rank."""
    settings = get_settings()
    rank = settings.severity_priority_rank.get(
        (severity or "").lower(), settings.default_severity_rank
    )
    return rank * 1e15 + time.time()


async def run_dispatch_consumer(stop_event: asyncio.Event) -> None:
    settings = get_settings()
    bus = get_event_bus()
    queue = get_priority_queue()
    await bus.connect()
    await queue.connect()
    if not bus.available:
        logger.warning("dispatch_consumer_disabled_no_redis")
        return

    await bus.ensure_group(settings.context_collected_stream, settings.dispatch_consumer_group)
    logger.info(
        "dispatch_consumer_started",
        stream=settings.context_collected_stream,
        group=settings.dispatch_consumer_group,
    )

    while not stop_event.is_set():
        entries = await bus.consume(
            settings.context_collected_stream,
            settings.dispatch_consumer_group,
            _consumer_name,
            block_ms=3000,
        )
        for entry_id, fields in entries:
            incident_id = fields.get("incident_id")
            severity = fields.get("severity") or "unknown"
            if not incident_id:
                logger.warning("dispatch_entry_missing_incident_id", entry_id=entry_id)
            else:
                task = json.dumps({"incident_id": incident_id, "severity": severity})
                enqueued = await queue.enqueue(
                    settings.investigation_queue_name, task, priority_score(severity)
                )
                logger.info(
                    "incident_enqueued",
                    incident_id=incident_id,
                    severity=severity,
                    enqueued=enqueued,
                )
                depth = await queue.size(settings.investigation_queue_name)
                INVESTIGATION_QUEUE_DEPTH.set(depth)
            # Enqueue (or the decision to drop a malformed entry) is the
            # durable step from here on; ack either way so the stream
            # doesn't redeliver something already handed to the queue.
            await bus.ack(settings.context_collected_stream, settings.dispatch_consumer_group, entry_id)
        if not entries:
            await asyncio.sleep(0.1)

    await bus.close()
    logger.info("dispatch_consumer_stopped")


async def _process_investigation_task(raw: str, *, worker_id: int) -> bool:
    """Handle one dequeued task. Returns True if it was handled (including
    permanent failures logged and dropped), False only for a malformed
    payload that couldn't even be parsed -- both cases are terminal for this
    item either way, since it's already out of the queue by the time this
    runs (ZPOPMIN is destructive); the return value is for test assertions
    and metrics, not a retry decision."""
    from app.services.orchestrator import run_investigation

    log = logger.bind(worker_id=worker_id)
    try:
        task = json.loads(raw)
        incident_id = uuid.UUID(task["incident_id"])
        severity = task.get("severity", "unknown")
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        log.warning("investigation_task_malformed", raw=raw, error=str(exc))
        return False

    INVESTIGATIONS_DEQUEUED_TOTAL.labels(severity=severity).inc()
    settings = get_settings()
    queue = get_priority_queue()
    depth = await queue.size(settings.investigation_queue_name)
    INVESTIGATION_QUEUE_DEPTH.set(depth)

    factory = get_session_factory()
    async with factory() as session:
        try:
            run = await run_investigation(session, incident_id)
            await session.commit()
            log.info(
                "investigation_worker_completed",
                incident_id=str(incident_id),
                investigation_id=str(run.id),
                status=run.status,
                used_fallback=run.used_fallback,
            )
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            log.warning(
                "investigation_worker_failed",
                incident_id=str(incident_id),
                error=str(exc),
            )
    return True


async def run_investigation_worker(worker_id: int, stop_event: asyncio.Event) -> None:
    settings = get_settings()
    queue = get_priority_queue()
    log = logger.bind(worker_id=worker_id)
    log.info("investigation_worker_started")

    while not stop_event.is_set():
        if not queue.available:
            await asyncio.sleep(1.0)
            continue

        raw = await queue.dequeue(settings.investigation_queue_name)
        if raw is None:
            await asyncio.sleep(0.5)
            continue

        await _process_investigation_task(raw, worker_id=worker_id)

    log.info("investigation_worker_stopped")
