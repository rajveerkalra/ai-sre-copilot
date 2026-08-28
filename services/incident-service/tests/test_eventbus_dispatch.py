"""Context-collection dispatch: event bus first, direct HTTP only as fallback."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import sample_alertmanager_payload


class _FakeBus:
    def __init__(self, available: bool):
        self._available = available
        self.published: list[tuple[str, dict]] = []

    async def publish(self, stream, event):
        if not self._available:
            return None
        self.published.append((stream, event))
        return "1-0"


@pytest.mark.asyncio
async def test_publishes_to_event_bus_when_available(client):
    fake_bus = _FakeBus(available=True)
    with patch("app.api.webhooks.get_event_bus", return_value=fake_bus):
        with patch("app.api.webhooks.trigger_context_collection", new=AsyncMock()) as fallback:
            payload = sample_alertmanager_payload(alertname="EventBusTestAlert")
            r = await client.post("/webhooks/alertmanager", json=payload)
            assert r.status_code == 200

    assert len(fake_bus.published) == 1
    stream, event = fake_bus.published[0]
    assert stream == "incidents.created"
    assert event["alertname"] == "EventBusTestAlert"
    fallback.assert_not_called()  # bus handled it; no need for the HTTP fallback


@pytest.mark.asyncio
async def test_falls_back_to_direct_http_when_bus_unavailable(client):
    fake_bus = _FakeBus(available=False)
    with patch("app.api.webhooks.get_event_bus", return_value=fake_bus):
        with patch("app.api.webhooks.trigger_context_collection", new=AsyncMock()) as fallback:
            payload = sample_alertmanager_payload(alertname="EventBusDownTestAlert")
            r = await client.post("/webhooks/alertmanager", json=payload)
            assert r.status_code == 200

    assert fake_bus.published == []  # publish attempted, but bus was unavailable
    fallback.assert_called_once()
