"""Async event bus over Redis Streams.

Redis Streams (XADD / XREADGROUP / XACK) give durable, replayable,
consumer-group dispatch -- a message survives a consumer being down and gets
redelivered, instead of the fire-and-forget HTTP-call-in-a-background-task
pattern this replaced in incident-service (see eventbus_client.py there),
where a single failed request silently dropped the event with nothing to
retry it.

Redis was chosen over Kafka deliberately: at this project's real message
volume (a handful of incidents at a time on a single host) a Kafka broker is
a lot of operational weight -- memory, a second stateful service to run and
monitor, ZooKeeper/KRaft -- for no throughput this system will ever need.
Redis is already running here for caching, so this is marginal cost, not new
infrastructure. The publish/consume surface below is intentionally narrow so
a Kafka-backed implementation (e.g. aiokafka) could be dropped in behind the
same three methods later if real throughput ever justified it, without
touching any caller code.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class RedisStreamEventBus:
    """Thin async wrapper around Redis Streams. Soft-fails when Redis is
    unavailable -- `publish()` returns None rather than raising, so callers
    decide whether that's fatal (see incident-service's dispatch, which
    falls back to a direct HTTP call if the bus can't be reached)."""

    def __init__(self, redis_url: str, *, enabled: bool = True) -> None:
        self.redis_url = redis_url
        self.enabled = enabled
        self._client = None

    async def connect(self) -> None:
        if not self.enabled:
            return
        try:
            from redis import asyncio as aioredis

            self._client = aioredis.from_url(
                self.redis_url, encoding="utf-8", decode_responses=True
            )
            await self._client.ping()
            logger.info("eventbus_connected", url=self.redis_url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("eventbus_unavailable", error=str(exc))
            self._client = None

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def available(self) -> bool:
        return self.enabled and self._client is not None

    async def publish(self, stream: str, event: dict[str, Any]) -> str | None:
        """Publish an event onto `stream`. Returns the new entry ID, or None
        if the bus is unavailable -- never raises."""
        if not self.available:
            return None
        try:
            payload = {
                k: (v if isinstance(v, str) else json.dumps(v))
                for k, v in event.items()
            }
            # maxlen caps stream growth (approximate trim, cheap) -- this is
            # an event bus, not a permanent audit log; incident-service and
            # incident_service.models already persist the durable record.
            return await self._client.xadd(stream, payload, maxlen=10000, approximate=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("eventbus_publish_failed", stream=stream, error=str(exc))
            return None

    async def ensure_group(self, stream: str, group: str) -> None:
        """Idempotent consumer-group creation; safe to call on every startup."""
        if not self.available:
            return
        try:
            await self._client.xgroup_create(stream, group, id="0", mkstream=True)
        except Exception as exc:  # noqa: BLE001
            if "BUSYGROUP" not in str(exc):
                logger.warning(
                    "eventbus_group_create_failed", stream=stream, group=group, error=str(exc)
                )

    async def consume(
        self,
        stream: str,
        group: str,
        consumer: str,
        *,
        block_ms: int = 5000,
        count: int = 10,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Read new entries for this consumer group. Caller must call ack()
        after successfully processing each entry -- unacked entries stay in
        the group's pending-entries list and can be redelivered."""
        if not self.available:
            return []
        try:
            resp = await self._client.xreadgroup(
                group, consumer, {stream: ">"}, count=count, block=block_ms
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("eventbus_consume_failed", stream=stream, error=str(exc))
            return []

        entries: list[tuple[str, dict[str, Any]]] = []
        for _stream_name, messages in resp or []:
            for entry_id, fields in messages:
                decoded: dict[str, Any] = {}
                for k, v in fields.items():
                    try:
                        decoded[k] = json.loads(v)
                    except (json.JSONDecodeError, TypeError):
                        decoded[k] = v
                entries.append((entry_id, decoded))
        return entries

    async def ack(self, stream: str, group: str, entry_id: str) -> None:
        if not self.available:
            return
        try:
            await self._client.xack(stream, group, entry_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("eventbus_ack_failed", stream=stream, entry_id=entry_id, error=str(exc))
