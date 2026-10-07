"""Incident creation fires outbound notifications via NotificationDispatcher."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import sample_alertmanager_payload


class _FakeDispatcher:
    def __init__(self, *, any_enabled: bool):
        self.any_enabled = any_enabled
        self.calls: list[dict] = []

    async def notify_incident_created(self, **kwargs):
        self.calls.append(kwargs)
        return {"slack": False, "webhook": True, "email": False}


@pytest.mark.asyncio
async def test_new_incident_dispatches_notification_when_configured(client):
    fake_dispatcher = _FakeDispatcher(any_enabled=True)
    with patch("app.api.webhooks.get_event_bus") as get_bus:
        get_bus.return_value.publish = AsyncMock(return_value="1-0")
        with patch(
            "app.api.webhooks.get_notification_dispatcher",
            return_value=fake_dispatcher,
        ):
            payload = sample_alertmanager_payload(alertname="NotifyTestAlert")
            r = await client.post("/webhooks/alertmanager", json=payload)
            assert r.status_code == 200

    assert len(fake_dispatcher.calls) == 1
    call = fake_dispatcher.calls[0]
    assert call["alertname"] == "NotifyTestAlert"
    assert "incident_id" in call
    assert "severity" in call


@pytest.mark.asyncio
async def test_no_notification_dispatch_when_nothing_configured(client):
    fake_dispatcher = _FakeDispatcher(any_enabled=False)
    with patch("app.api.webhooks.get_event_bus") as get_bus:
        get_bus.return_value.publish = AsyncMock(return_value="1-0")
        with patch(
            "app.api.webhooks.get_notification_dispatcher",
            return_value=fake_dispatcher,
        ):
            payload = sample_alertmanager_payload(alertname="NotifyDisabledTestAlert")
            r = await client.post("/webhooks/alertmanager", json=payload)
            assert r.status_code == 200

    assert fake_dispatcher.calls == []


@pytest.mark.asyncio
async def test_deduplicated_alert_does_not_dispatch_notification(client):
    fake_dispatcher = _FakeDispatcher(any_enabled=True)
    with patch("app.api.webhooks.get_event_bus") as get_bus:
        get_bus.return_value.publish = AsyncMock(return_value="1-0")
        with patch(
            "app.api.webhooks.get_notification_dispatcher",
            return_value=fake_dispatcher,
        ):
            payload = sample_alertmanager_payload(alertname="DedupNotifyTestAlert")
            r1 = await client.post("/webhooks/alertmanager", json=payload)
            assert r1.status_code == 200
            r2 = await client.post("/webhooks/alertmanager", json=payload)
            assert r2.status_code == 200

    # Only the first (created) alert should have triggered a notification --
    # the second (deduplicated) must not re-notify.
    assert len(fake_dispatcher.calls) == 1
