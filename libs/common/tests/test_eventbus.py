"""RedisStreamEventBus -- soft-fail behavior and the publish/consume/ack cycle."""

from __future__ import annotations

import pytest

from libs.common.eventbus import RedisStreamEventBus


class _FakeAioRedis:
    """Minimal in-memory stand-in for redis.asyncio's stream commands."""

    def __init__(self):
        self.streams: dict[str, list[tuple[str, dict]]] = {}
        self.groups: dict[tuple[str, str], set[str]] = {}
        self._seq = 0

    async def ping(self):
        return True

    async def aclose(self):
        pass

    async def xadd(self, stream, payload, maxlen=None, approximate=None):
        self._seq += 1
        entry_id = f"{self._seq}-0"
        self.streams.setdefault(stream, []).append((entry_id, dict(payload)))
        return entry_id

    async def xgroup_create(self, stream, group, id="0", mkstream=False):
        self.groups[(stream, group)] = set()

    async def xreadgroup(self, group, consumer, streams, count=10, block=5000):
        [(stream, _marker)] = streams.items()
        delivered = self.groups.get((stream, group), set())
        pending = [
            (eid, fields) for eid, fields in self.streams.get(stream, []) if eid not in delivered
        ][:count]
        for eid, _ in pending:
            delivered.add(eid)
        if not pending:
            return []
        return [(stream, pending)]

    async def xack(self, stream, group, entry_id):
        return 1


@pytest.fixture
def fake_redis(monkeypatch):
    fake = _FakeAioRedis()

    class _Module:
        @staticmethod
        def from_url(*args, **kwargs):
            return fake

    monkeypatch.setattr("redis.asyncio", _Module)
    return fake


@pytest.mark.asyncio
async def test_disabled_bus_never_touches_redis():
    bus = RedisStreamEventBus("redis://unused", enabled=False)
    await bus.connect()
    assert bus.available is False
    assert await bus.publish("incidents.created", {"incident_id": "x"}) is None
    assert await bus.consume("incidents.created", "g", "c") == []


@pytest.mark.asyncio
async def test_connect_failure_is_soft(monkeypatch):
    class _Boom:
        @staticmethod
        def from_url(*a, **k):
            raise ConnectionError("no redis here")

    monkeypatch.setattr("redis.asyncio", _Boom)
    bus = RedisStreamEventBus("redis://nope", enabled=True)
    await bus.connect()  # must not raise
    assert bus.available is False
    assert await bus.publish("s", {"a": 1}) is None


@pytest.mark.asyncio
async def test_publish_consume_ack_roundtrip(fake_redis):
    bus = RedisStreamEventBus("redis://fake", enabled=True)
    await bus.connect()
    assert bus.available is True

    await bus.ensure_group("incidents.created", "context-collectors")
    entry_id = await bus.publish(
        "incidents.created",
        {"incident_id": "abc-123", "severity": "critical", "labels": {"service": "sample-app"}},
    )
    assert entry_id is not None

    entries = await bus.consume("incidents.created", "context-collectors", "worker-1")
    assert len(entries) == 1
    got_id, fields = entries[0]
    assert got_id == entry_id
    assert fields["incident_id"] == "abc-123"
    assert fields["labels"] == {"service": "sample-app"}  # JSON round-tripped, not left as a string

    # not yet acked -> a second read from a fresh consumer sees nothing new
    # (already delivered to worker-1's pending list, not redelivered as "new")
    more = await bus.consume("incidents.created", "context-collectors", "worker-2")
    assert more == []

    await bus.ack("incidents.created", "context-collectors", entry_id)


@pytest.mark.asyncio
async def test_ensure_group_is_idempotent(fake_redis):
    bus = RedisStreamEventBus("redis://fake", enabled=True)
    await bus.connect()
    await bus.ensure_group("s", "g")
    await bus.ensure_group("s", "g")  # must not raise on the second call
