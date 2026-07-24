"""Collector contracts and retry wrapper."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.config import Settings, get_settings
from app.metrics import (
    COLLECTOR_DURATION_SECONDS,
    COLLECTOR_ERRORS_TOTAL,
    COLLECTOR_LATENCY,
    COLLECTOR_SUCCESS_TOTAL,
)

logger = structlog.get_logger(__name__)


@dataclass
class CollectionRequest:
    """Inputs shared by all collectors for one investigation."""

    incident_id: str
    correlation_id: str
    service: str = "sample-app"
    namespace: str = "default"
    alertname: str = ""
    severity: str = ""
    labels: dict[str, str] = field(default_factory=dict)
    incident_created_at: str | None = None


@dataclass
class CollectorResult:
    collector_name: str
    status: str  # success | failed | skipped
    duration_ms: float
    attempt_count: int
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)


class BaseCollector(ABC):
    name: str = "base"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @abstractmethod
    async def collect(self, request: CollectionRequest) -> dict[str, Any]:
        """Return normalized collector payload. Raise on hard failure."""

    async def run(self, request: CollectionRequest) -> CollectorResult:
        """Execute with retries and exponential backoff. Never raises."""
        retries = max(1, self.settings.collector_retries)
        backoff = self.settings.collector_backoff_base_seconds
        errors: list[dict[str, Any]] = []
        started = time.perf_counter()
        last_error: str | None = None

        for attempt in range(1, retries + 1):
            attempt_started = time.perf_counter()
            try:
                data = await asyncio.wait_for(
                    self.collect(request),
                    timeout=self.settings.collector_timeout_seconds,
                )
                attempt_ms = (time.perf_counter() - attempt_started) * 1000
                COLLECTOR_LATENCY.labels(
                    collector_name=self.name, attempt=str(attempt)
                ).observe(attempt_ms / 1000.0)
                duration_ms = (time.perf_counter() - started) * 1000
                COLLECTOR_DURATION_SECONDS.labels(
                    collector_name=self.name, status="success"
                ).observe(duration_ms / 1000.0)
                COLLECTOR_SUCCESS_TOTAL.labels(collector_name=self.name).inc()
                logger.info(
                    "collector_success",
                    collector_name=self.name,
                    incident_id=request.incident_id,
                    correlation_id=request.correlation_id,
                    duration_ms=round(duration_ms, 2),
                    status="success",
                    attempt=attempt,
                )
                return CollectorResult(
                    collector_name=self.name,
                    status="success",
                    duration_ms=round(duration_ms, 2),
                    attempt_count=attempt,
                    data=data or {},
                    errors=errors,
                )
            except Exception as exc:  # noqa: BLE001 — collectors must not crash orchestrator
                attempt_ms = (time.perf_counter() - attempt_started) * 1000
                COLLECTOR_LATENCY.labels(
                    collector_name=self.name, attempt=str(attempt)
                ).observe(attempt_ms / 1000.0)
                last_error = f"{type(exc).__name__}: {exc}"
                errors.append(
                    {
                        "attempt": attempt,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    }
                )
                logger.warning(
                    "collector_attempt_failed",
                    collector_name=self.name,
                    incident_id=request.incident_id,
                    correlation_id=request.correlation_id,
                    attempt=attempt,
                    error=last_error,
                    duration_ms=round(attempt_ms, 2),
                    status="failed",
                )
                if attempt < retries:
                    await asyncio.sleep(backoff * (2 ** (attempt - 1)))

        duration_ms = (time.perf_counter() - started) * 1000
        COLLECTOR_DURATION_SECONDS.labels(
            collector_name=self.name, status="failed"
        ).observe(duration_ms / 1000.0)
        COLLECTOR_ERRORS_TOTAL.labels(collector_name=self.name).inc()
        logger.error(
            "collector_failed",
            collector_name=self.name,
            incident_id=request.incident_id,
            correlation_id=request.correlation_id,
            duration_ms=round(duration_ms, 2),
            status="failed",
            error=last_error,
        )
        return CollectorResult(
            collector_name=self.name,
            status="failed",
            duration_ms=round(duration_ms, 2),
            attempt_count=retries,
            data={"available": False, "error": last_error},
            error=last_error,
            errors=errors,
        )
