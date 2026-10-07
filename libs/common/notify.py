"""Outbound notifications: Slack, generic webhook, email.

Three independent, individually-optional backends, fanned out by
`NotificationDispatcher`. Every backend follows the same rule the rest of
this codebase already uses for external calls (Redis, model-gateway,
knowledge-service): unconfigured or unreachable is a soft failure, logged
and swallowed, never raised into the caller. A notification is a
side-effect of something that already happened (an incident was created, an
RCA completed) -- it must never be able to fail the thing it's reporting on.

Real, live-verified delivery paths:
- Slack: POSTs the exact payload format Slack's Incoming Webhooks expect
  (`{"text": ...}`). Verified against this project's own webhook-sink
  service (same wire format a real Slack webhook receiver would get); real
  delivery to an actual Slack workspace requires the user's own webhook URL
  in SLACK_WEBHOOK_URL -- never fabricate or guess one.
- Webhook: generic JSON POST to any configured URL. Verified live against
  webhook-sink.
- Email: real SMTP via smtplib. Verified live against a local MailHog
  instance (docker-compose's `mailhog` service) -- a real SMTP conversation,
  not mocked.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class NotifyConfig:
    slack_webhook_url: str = ""
    webhook_url: str = ""
    smtp_host: str = ""
    smtp_port: int = 25
    smtp_from: str = "ai-sre-copilot@localhost"
    smtp_to: str = ""
    smtp_use_tls: bool = False
    smtp_username: str = ""
    smtp_password: str = ""
    timeout_seconds: float = 5.0


class SlackNotifier:
    def __init__(self, config: NotifyConfig) -> None:
        self.config = config

    @property
    def enabled(self) -> bool:
        return bool(self.config.slack_webhook_url)

    async def send(self, *, title: str, lines: list[str]) -> bool:
        if not self.enabled:
            return False
        text = f"*{title}*\n" + "\n".join(f"- {line}" for line in lines)
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                resp = await client.post(self.config.slack_webhook_url, json={"text": text})
                ok = resp.status_code < 400
                if not ok:
                    logger.warning("slack_notify_failed", status_code=resp.status_code, body=resp.text[:200])
                return ok
        except Exception as exc:  # noqa: BLE001
            logger.warning("slack_notify_error", error=str(exc))
            return False


class WebhookNotifier:
    def __init__(self, config: NotifyConfig) -> None:
        self.config = config

    @property
    def enabled(self) -> bool:
        return bool(self.config.webhook_url)

    async def send(self, *, event: str, data: dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                resp = await client.post(self.config.webhook_url, json={"event": event, "data": data})
                ok = resp.status_code < 400
                if not ok:
                    logger.warning("webhook_notify_failed", status_code=resp.status_code, body=resp.text[:200])
                return ok
        except Exception as exc:  # noqa: BLE001
            logger.warning("webhook_notify_error", error=str(exc))
            return False


class EmailNotifier:
    def __init__(self, config: NotifyConfig) -> None:
        self.config = config

    @property
    def enabled(self) -> bool:
        return bool(self.config.smtp_host and self.config.smtp_to)

    def _send_sync(self, *, subject: str, body: str) -> bool:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self.config.smtp_from
        msg["To"] = self.config.smtp_to
        try:
            with smtplib.SMTP(
                self.config.smtp_host, self.config.smtp_port, timeout=self.config.timeout_seconds
            ) as server:
                if self.config.smtp_use_tls:
                    server.starttls()
                if self.config.smtp_username:
                    server.login(self.config.smtp_username, self.config.smtp_password)
                server.send_message(msg)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("email_notify_error", error=str(exc))
            return False

    async def send(self, *, subject: str, body: str) -> bool:
        if not self.enabled:
            return False
        # smtplib is synchronous; run off the event loop so a slow/unreachable
        # SMTP server can't stall the request handling this notification.
        import asyncio

        return await asyncio.to_thread(self._send_sync, subject=subject, body=body)


@dataclass
class NotificationDispatcher:
    """Fans out one logical event to every configured backend. Each backend
    is independent -- one failing or being unconfigured never affects the
    others, and dispatch always returns (never raises) so callers can fire
    it without wrapping every call site in their own try/except."""

    config: NotifyConfig
    slack: SlackNotifier = field(init=False)
    webhook: WebhookNotifier = field(init=False)
    email: EmailNotifier = field(init=False)

    def __post_init__(self) -> None:
        self.slack = SlackNotifier(self.config)
        self.webhook = WebhookNotifier(self.config)
        self.email = EmailNotifier(self.config)

    @property
    def any_enabled(self) -> bool:
        return self.slack.enabled or self.webhook.enabled or self.email.enabled

    async def notify_incident_created(
        self, *, incident_id: str, title: str, severity: str, service: str, alertname: str
    ) -> dict[str, bool]:
        lines = [f"Service: {service}", f"Severity: {severity}", f"Alert: {alertname}", f"Incident: {incident_id}"]
        results = {
            "slack": await self.slack.send(title=f"New incident: {title}", lines=lines),
            "webhook": await self.webhook.send(
                event="incident.created",
                data={
                    "incident_id": incident_id,
                    "title": title,
                    "severity": severity,
                    "service": service,
                    "alertname": alertname,
                },
            ),
            "email": await self.email.send(
                subject=f"[AI SRE Copilot] New incident: {title}",
                body="\n".join(lines),
            ),
        }
        logger.info("incident_notification_dispatched", incident_id=incident_id, results=results)
        return results

    async def notify_rca_complete(
        self, *, incident_id: str, investigation_id: str, root_cause: str, confidence: float, used_fallback: bool
    ) -> dict[str, bool]:
        lines = [
            f"Root cause: {root_cause}",
            f"Confidence: {confidence}%",
            f"Method: {'rule-based fallback' if used_fallback else 'LLM synthesis'}",
            f"Investigation: {investigation_id}",
        ]
        results = {
            "slack": await self.slack.send(title=f"RCA complete for incident {incident_id}", lines=lines),
            "webhook": await self.webhook.send(
                event="rca.completed",
                data={
                    "incident_id": incident_id,
                    "investigation_id": investigation_id,
                    "root_cause": root_cause,
                    "confidence": confidence,
                    "used_fallback": used_fallback,
                },
            ),
            "email": await self.email.send(
                subject=f"[AI SRE Copilot] RCA complete: {root_cause}",
                body="\n".join(lines),
            ),
        }
        logger.info("rca_notification_dispatched", incident_id=incident_id, results=results)
        return results
