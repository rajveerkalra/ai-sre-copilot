"""Notification backends -- soft-fail behavior, correct payload shapes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from libs.common.notify import NotificationDispatcher, NotifyConfig


def _config(**overrides) -> NotifyConfig:
    return NotifyConfig(**overrides)


# --- Slack -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slack_disabled_without_webhook_url():
    dispatcher = NotificationDispatcher(_config())
    assert dispatcher.slack.enabled is False
    assert await dispatcher.slack.send(title="t", lines=["a"]) is False


@pytest.mark.asyncio
async def test_slack_sends_correct_incoming_webhook_shape():
    dispatcher = NotificationDispatcher(_config(slack_webhook_url="https://hooks.slack.com/services/x"))
    captured = {}

    class _Resp:
        status_code = 200
        text = ""

    async def fake_post(url, json=None):
        captured["url"] = url
        captured["json"] = json
        return _Resp()

    fake_client = MagicMock()
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)
    fake_client.post = fake_post

    with patch("httpx.AsyncClient", return_value=fake_client):
        ok = await dispatcher.slack.send(title="New incident", lines=["Severity: critical"])

    assert ok is True
    assert captured["url"] == "https://hooks.slack.com/services/x"
    assert "text" in captured["json"]  # Slack Incoming Webhooks require this exact key
    assert "New incident" in captured["json"]["text"]
    assert "Severity: critical" in captured["json"]["text"]


@pytest.mark.asyncio
async def test_slack_non_2xx_is_a_soft_failure():
    dispatcher = NotificationDispatcher(_config(slack_webhook_url="https://hooks.slack.com/services/x"))

    class _Resp:
        status_code = 404
        text = "no_service"

    fake_client = MagicMock()
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)
    fake_client.post = AsyncMock(return_value=_Resp())

    with patch("httpx.AsyncClient", return_value=fake_client):
        ok = await dispatcher.slack.send(title="t", lines=["a"])
    assert ok is False


@pytest.mark.asyncio
async def test_slack_network_error_is_a_soft_failure():
    dispatcher = NotificationDispatcher(_config(slack_webhook_url="https://hooks.slack.com/services/x"))

    fake_client = MagicMock()
    fake_client.__aenter__ = AsyncMock(side_effect=ConnectionError("no network"))

    with patch("httpx.AsyncClient", return_value=fake_client):
        ok = await dispatcher.slack.send(title="t", lines=["a"])
    assert ok is False


# --- Generic webhook -----------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_disabled_without_url():
    dispatcher = NotificationDispatcher(_config())
    assert dispatcher.webhook.enabled is False
    assert await dispatcher.webhook.send(event="e", data={}) is False


@pytest.mark.asyncio
async def test_webhook_sends_event_and_data():
    dispatcher = NotificationDispatcher(_config(webhook_url="http://webhook-sink:9000/notifications"))
    captured = {}

    class _Resp:
        status_code = 200
        text = ""

    async def fake_post(url, json=None):
        captured["url"] = url
        captured["json"] = json
        return _Resp()

    fake_client = MagicMock()
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)
    fake_client.post = fake_post

    with patch("httpx.AsyncClient", return_value=fake_client):
        ok = await dispatcher.webhook.send(event="incident.created", data={"incident_id": "abc"})

    assert ok is True
    assert captured["json"]["event"] == "incident.created"
    assert captured["json"]["data"]["incident_id"] == "abc"


# --- Email ---------------------------------------------------------------------


def test_email_disabled_without_smtp_host_or_recipient():
    dispatcher = NotificationDispatcher(_config(smtp_host="", smtp_to=""))
    assert dispatcher.email.enabled is False

    dispatcher2 = NotificationDispatcher(_config(smtp_host="mailhog", smtp_to=""))
    assert dispatcher2.email.enabled is False  # host without a recipient is still disabled


@pytest.mark.asyncio
async def test_email_sends_via_smtp_with_correct_headers():
    dispatcher = NotificationDispatcher(
        _config(smtp_host="mailhog", smtp_port=1025, smtp_to="ops@example.com", smtp_from="copilot@example.com")
    )
    sent_messages = []

    class _FakeSMTP:
        def __init__(self, host, port, timeout=None):
            assert host == "mailhog"
            assert port == 1025

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            pass

        def login(self, user, password):
            pass

        def send_message(self, msg):
            sent_messages.append(msg)

    with patch("smtplib.SMTP", _FakeSMTP):
        ok = await dispatcher.email.send(subject="Test subject", body="Test body")

    assert ok is True
    assert len(sent_messages) == 1
    assert sent_messages[0]["Subject"] == "Test subject"
    assert sent_messages[0]["From"] == "copilot@example.com"
    assert sent_messages[0]["To"] == "ops@example.com"


@pytest.mark.asyncio
async def test_email_smtp_error_is_a_soft_failure():
    dispatcher = NotificationDispatcher(_config(smtp_host="mailhog", smtp_to="ops@example.com"))

    class _FakeSMTP:
        def __init__(self, *a, **k):
            raise ConnectionRefusedError("smtp down")

    with patch("smtplib.SMTP", _FakeSMTP):
        ok = await dispatcher.email.send(subject="s", body="b")
    assert ok is False


# --- Dispatcher fan-out ---------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatcher_any_enabled_reflects_configured_backends():
    assert NotificationDispatcher(_config()).any_enabled is False
    assert NotificationDispatcher(_config(webhook_url="http://x")).any_enabled is True


@pytest.mark.asyncio
async def test_notify_incident_created_never_raises_when_nothing_configured():
    dispatcher = NotificationDispatcher(_config())
    results = await dispatcher.notify_incident_created(
        incident_id="abc", title="High error rate", severity="critical", service="sample-app", alertname="X"
    )
    assert results == {"slack": False, "webhook": False, "email": False}


@pytest.mark.asyncio
async def test_notify_rca_complete_never_raises_when_nothing_configured():
    dispatcher = NotificationDispatcher(_config())
    results = await dispatcher.notify_rca_complete(
        incident_id="abc",
        investigation_id="inv-1",
        root_cause="Elevated error rate",
        confidence=85.0,
        used_fallback=True,
    )
    assert results == {"slack": False, "webhook": False, "email": False}
