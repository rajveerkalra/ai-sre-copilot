"""Singleton RedisStreamEventBus for this service, plus lifecycle hooks."""

from __future__ import annotations

from app.config import get_settings

try:
    from libs.common.eventbus import RedisStreamEventBus
except ImportError:  # pragma: no cover
    from common.eventbus import RedisStreamEventBus  # type: ignore

_bus: RedisStreamEventBus | None = None


def get_event_bus() -> RedisStreamEventBus:
    global _bus
    if _bus is None:
        settings = get_settings()
        _bus = RedisStreamEventBus(settings.redis_url, enabled=settings.event_bus_enabled)
    return _bus


async def connect_event_bus() -> None:
    await get_event_bus().connect()


async def close_event_bus() -> None:
    bus = get_event_bus()
    await bus.close()
