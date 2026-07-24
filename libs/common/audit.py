"""Structured audit event helpers (immutable log stream)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger("audit")


def emit_audit(
    *,
    action: str,
    actor: str,
    resource_type: str,
    resource_id: str | None = None,
    outcome: str = "success",
    detail: dict[str, Any] | None = None,
    service: str | None = None,
) -> dict[str, Any]:
    """Emit an immutable audit event to structured logs (and optional sinks)."""
    event = {
        "audit": True,
        "action": action,
        "actor": actor,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "outcome": outcome,
        "detail": detail or {},
        "service": service,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("audit_event", **{k: v for k, v in event.items() if k != "audit"}, audit=True)
    return event
