"""Orchestrates collectors into a normalized Investigation Context."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.collectors import ALL_COLLECTORS, CollectionRequest, CollectorResult
from app.config import get_settings
from app.db.base import utcnow
from app.metrics import COLLECTION_RUNS_TOTAL
from app.models import (
    CollectorError,
    CollectorRun,
    CollectorRunStatus,
    ContextStatus,
    InvestigationContext,
)

logger = structlog.get_logger(__name__)


class ContextNotFoundError(Exception):
    def __init__(self, incident_id: uuid.UUID) -> None:
        self.incident_id = incident_id
        super().__init__(f"No investigation context for incident {incident_id}")


class IncidentLookupError(Exception):
    pass


async def fetch_incident_metadata(incident_id: uuid.UUID) -> dict[str, Any]:
    """Pull incident metadata from incident-service (best effort)."""
    settings = get_settings()
    url = f"{settings.incident_service_url.rstrip('/')}/incidents/{incident_id}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            if resp.status_code == 404:
                raise IncidentLookupError(f"Incident {incident_id} not found")
            resp.raise_for_status()
            return resp.json()
    except IncidentLookupError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "incident_metadata_fetch_failed",
            incident_id=str(incident_id),
            error=str(exc),
        )
        return {
            "id": str(incident_id),
            "service": settings.default_service,
            "alertname": "",
            "severity": "unknown",
            "namespace": "default",
        }


async def collect_for_incident(
    db: AsyncSession,
    incident_id: uuid.UUID,
    *,
    correlation_id: str | None = None,
    force: bool = False,
) -> InvestigationContext:
    settings = get_settings()
    correlation_id = correlation_id or str(uuid.uuid4())
    meta = await fetch_incident_metadata(incident_id)

    existing = await _latest_context(db, incident_id)
    if existing and existing.status == ContextStatus.RUNNING and not force:
        return existing

    ctx = InvestigationContext(
        incident_id=incident_id,
        status=ContextStatus.RUNNING,
        correlation_id=correlation_id,
        context={},
        metrics={},
        logs={},
        kubernetes={},
        deployment={},
        system={},
        metadata_={
            "incident": {
                "id": str(incident_id),
                "title": meta.get("title"),
                "status": meta.get("status"),
                "severity": meta.get("severity"),
                "alertname": meta.get("alertname"),
                "service": meta.get("service"),
                "namespace": meta.get("namespace"),
                "fingerprint": meta.get("fingerprint"),
                "created_at": meta.get("created_at"),
            },
            "triggered_by": "context-service",
        },
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(ctx)
    await db.flush()

    request = CollectionRequest(
        incident_id=str(incident_id),
        correlation_id=correlation_id,
        service=meta.get("service") or settings.default_service,
        namespace=meta.get("namespace") or settings.kubernetes_namespace,
        alertname=meta.get("alertname") or "",
        severity=meta.get("severity") or "",
        labels={
            "service": meta.get("service") or settings.default_service,
            "alertname": meta.get("alertname") or "",
            "severity": meta.get("severity") or "",
        },
        incident_created_at=meta.get("created_at"),
    )

    started = time.perf_counter()
    collectors = [cls(settings) for cls in ALL_COLLECTORS]
    results: list[CollectorResult] = await asyncio.gather(
        *[c.run(request) for c in collectors]
    )

    by_name = {r.collector_name: r for r in results}
    metrics = by_name.get("metrics")
    logs = by_name.get("logs")
    kubernetes = by_name.get("kubernetes")
    deployment = by_name.get("deployment")
    system = by_name.get("system")

    for result in results:
        run = CollectorRun(
            investigation_context_id=ctx.id,
            collector_name=result.collector_name,
            status=(
                CollectorRunStatus.SUCCESS
                if result.status == "success"
                else CollectorRunStatus.FAILED
                if result.status == "failed"
                else CollectorRunStatus.SKIPPED
            ),
            attempt_count=result.attempt_count,
            started_at=utcnow(),
            finished_at=utcnow(),
            duration_ms=result.duration_ms,
            output=result.data,
        )
        db.add(run)
        await db.flush()
        for err in result.errors:
            db.add(
                CollectorError(
                    collector_run_id=run.id,
                    attempt=int(err.get("attempt", 0)),
                    error_message=str(err.get("error_message", "")),
                    error_type=err.get("error_type"),
                    created_at=utcnow(),
                )
            )

    duration_ms = (time.perf_counter() - started) * 1000
    success_count = sum(1 for r in results if r.status == "success")
    fail_count = sum(1 for r in results if r.status == "failed")

    if fail_count == 0:
        status = ContextStatus.COMPLETED
    elif success_count == 0:
        status = ContextStatus.FAILED
    else:
        status = ContextStatus.PARTIAL

    normalized = {
        "incident_id": str(incident_id),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "status": status.value,
        "metrics": (metrics.data if metrics else {}),
        "logs": (logs.data if logs else {}),
        "kubernetes": (kubernetes.data if kubernetes else {}),
        "deployment": (deployment.data if deployment else {}),
        "system": (system.data if system else {}),
        "metadata": {
            **(ctx.metadata_ or {}),
            "collector_statuses": {
                r.collector_name: r.status for r in results
            },
            "duration_ms": round(duration_ms, 2),
        },
    }

    ctx.status = status
    ctx.collected_at = utcnow()
    ctx.duration_ms = round(duration_ms, 2)
    ctx.context = normalized
    ctx.metrics = normalized["metrics"]
    ctx.logs = normalized["logs"]
    ctx.kubernetes = normalized["kubernetes"]
    ctx.deployment = normalized["deployment"]
    ctx.system = normalized["system"]
    ctx.metadata_ = normalized["metadata"]
    ctx.updated_at = utcnow()

    COLLECTION_RUNS_TOTAL.labels(status=status.value).inc()
    await db.flush()

    logger.info(
        "context_collection_complete",
        incident_id=str(incident_id),
        correlation_id=correlation_id,
        status=status.value,
        duration_ms=round(duration_ms, 2),
        success_count=success_count,
        fail_count=fail_count,
    )
    return ctx


async def get_latest_context(
    db: AsyncSession, incident_id: uuid.UUID
) -> InvestigationContext:
    ctx = await _latest_context(db, incident_id, with_runs=True)
    if ctx is None:
        raise ContextNotFoundError(incident_id)
    return ctx


async def _latest_context(
    db: AsyncSession,
    incident_id: uuid.UUID,
    *,
    with_runs: bool = False,
) -> InvestigationContext | None:
    stmt = (
        select(InvestigationContext)
        .where(InvestigationContext.incident_id == incident_id)
        .order_by(InvestigationContext.created_at.desc())
        .limit(1)
    )
    if with_runs:
        stmt = stmt.options(
            selectinload(InvestigationContext.collector_runs).selectinload(
                CollectorRun.errors
            )
        )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
