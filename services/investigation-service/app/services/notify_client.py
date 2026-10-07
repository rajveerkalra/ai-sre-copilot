"""Singleton NotificationDispatcher built from this service's settings."""

from __future__ import annotations

from app.config import get_settings

try:
    from libs.common.notify import NotificationDispatcher, NotifyConfig
except ImportError:  # pragma: no cover
    from common.notify import NotificationDispatcher, NotifyConfig  # type: ignore

_dispatcher: NotificationDispatcher | None = None


def get_notification_dispatcher() -> NotificationDispatcher:
    global _dispatcher
    if _dispatcher is None:
        settings = get_settings()
        _dispatcher = NotificationDispatcher(
            NotifyConfig(
                slack_webhook_url=settings.slack_webhook_url,
                webhook_url=settings.notify_webhook_url,
                smtp_host=settings.smtp_host,
                smtp_port=settings.smtp_port,
                smtp_from=settings.smtp_from,
                smtp_to=settings.smtp_to,
                smtp_use_tls=settings.smtp_use_tls,
                smtp_username=settings.smtp_username,
                smtp_password=settings.smtp_password,
            )
        )
    return _dispatcher
