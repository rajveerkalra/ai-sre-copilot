"""Investigation orchestration: fetch context → LangGraph → persist."""

from __future__ import annotations

import time
import uuid
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db.base import utcnow
from app.graph.workflow import investigation_graph
from app.metrics import INVESTIGATION_DURATION_SECONDS
from app.models import (
    AgentResult,
    Evidence,
    InvestigationRun,
    InvestigationStatus,
    RCAReport,
)
from app.services.evidence import build_evidence_catalog

logger = structlog.get_logger(__name__)


class InvestigationNotFoundError(Exception):
    def __init__(self, investigation_id: uuid.UUID) -> None:
        super().__init__(f"Investigation {investigation_id} not found")
        self.investigation_id = investigation_id


class ContextMissingError(Exception):
    pass


async def fetch_context(incident_id: uuid.UUID) -> dict[str, Any]:
    """Fetch Phase 3 context with Redis cache + resilient HTTP."""
    settings = get_settings()
    base = settings.context_service_url.rstrip("/")

    try:
        from libs.common.cache import RedisCache, cache_key
    except ImportError:  # pragma: no cover
        from common.cache import RedisCache, cache_key  # type: ignore

    from app.metrics import observe_cache

    cache = RedisCache(
        settings.redis_url,
        enabled=settings.cache_enabled,
        default_ttl_seconds=settings.context_cache_ttl_seconds,
    )
    await cache.connect()
    ckey = cache_key("context", str(incident_id), prefix="inv")
    try:
        cached = await cache.get_json(ckey)
        if cached is not None:
            observe_cache("investigation_context", True)
            return cached
        observe_cache("investigation_context", False)

        async with httpx.AsyncClient(timeout=120.0) as client:
            get_resp = await client.get(f"{base}/incidents/{incident_id}/context")
            if get_resp.status_code == 404 and settings.auto_collect_context_if_missing:
                collect = await client.post(
                    f"{base}/incidents/{incident_id}/collect",
                    json={"force": True},
                )
                if collect.status_code >= 400:
                    raise ContextMissingError(
                        f"Context collection failed: {collect.status_code} {collect.text[:200]}"
                    )
                get_resp = await client.get(f"{base}/incidents/{incident_id}/context")
            if get_resp.status_code == 404:
                raise ContextMissingError("No investigation context available")
            get_resp.raise_for_status()
            payload = get_resp.json()
            await cache.set_json(ckey, payload)
            return payload
    finally:
        await cache.close()


async def run_investigation(
    db: AsyncSession,
    incident_id: uuid.UUID,
    *,
    correlation_id: str | None = None,
) -> InvestigationRun:
    settings = get_settings()
    correlation_id = correlation_id or str(uuid.uuid4())
    started = time.perf_counter()

    run = InvestigationRun(
        incident_id=incident_id,
        status=InvestigationStatus.RUNNING,
        correlation_id=correlation_id,
        model_name=settings.llm_model,
        prompt_version=settings.prompt_version,
        used_fallback=False,
        started_at=utcnow(),
        report={},
        context_snapshot={},
    )
    db.add(run)
    await db.flush()

    try:
        ctx_payload = await fetch_context(incident_id)
        # Prefer nested context blob; fall back to top-level slices
        context = ctx_payload.get("context") or {
            "metrics": ctx_payload.get("metrics"),
            "logs": ctx_payload.get("logs"),
            "kubernetes": ctx_payload.get("kubernetes"),
            "deployment": ctx_payload.get("deployment"),
            "system": ctx_payload.get("system"),
            "metadata": ctx_payload.get("metadata"),
            "incident_id": str(incident_id),
        }
        run.context_snapshot = context
        evidence = build_evidence_catalog(context)

        initial_state = {
            "incident_id": str(incident_id),
            "investigation_id": str(run.id),
            "correlation_id": correlation_id,
            "context": context,
            "evidence": evidence,
            "errors": [],
        }
        final_state = await investigation_graph.ainvoke(initial_state)

        report = final_state.get("report") or {}
        rca = final_state.get("rca") or {}
        used_fallback = bool(final_state.get("used_fallback"))
        aggregated = final_state.get("aggregated_evidence") or evidence

        for e in aggregated:
            db.add(
                Evidence(
                    investigation_id=run.id,
                    evidence_id=e["evidence_id"],
                    source=e.get("source") or "unknown",
                    summary=e.get("summary") or "",
                    raw=e.get("raw") or {},
                    created_at=utcnow(),
                )
            )

        for agent_key, result in [
            ("metrics_investigator", final_state.get("metrics_result")),
            ("logs_investigator", final_state.get("logs_result")),
            ("kubernetes_investigator", final_state.get("kubernetes_result")),
            ("runbook_investigator", final_state.get("runbook_result")),
            ("rca_synthesizer", rca),
        ]:
            if not result:
                continue
            db.add(
                AgentResult(
                    investigation_id=run.id,
                    agent_name=agent_key,
                    status="success",
                    duration_ms=float(result.get("duration_ms") or 0),
                    confidence=(
                        float(result["confidence"])
                        if result.get("confidence") is not None
                        else None
                    ),
                    output=result,
                    used_llm=bool(
                        result.get("used_llm")
                        or result.get("method") in {"ollama", "model-gateway"}
                    ),
                    created_at=utcnow(),
                )
            )

        root_cause = rca.get("root_cause") or report.get("root_cause") or "Insufficient evidence"
        confidence = float(rca.get("confidence") or report.get("confidence") or 0)
        status = (
            InvestigationStatus.INSUFFICIENT_EVIDENCE
            if root_cause == "Insufficient evidence"
            else InvestigationStatus.COMPLETED
        )

        db.add(
            RCAReport(
                investigation_id=run.id,
                root_cause=root_cause,
                confidence=confidence,
                business_impact=str(rca.get("business_impact") or ""),
                next_steps=list(rca.get("next_steps") or report.get("suggested_actions") or []),
                evidence_ids=list(rca.get("evidence_ids") or report.get("evidence_ids") or []),
                unknowns=list(rca.get("unknowns") or report.get("unknowns") or []),
                supporting_runbooks=list(
                    rca.get("supporting_runbooks") or report.get("supporting_runbooks") or []
                ),
                used_fallback=used_fallback,
                full_report=report,
                created_at=utcnow(),
            )
        )

        duration_ms = (time.perf_counter() - started) * 1000
        run.status = status
        run.used_fallback = used_fallback
        run.confidence = confidence
        run.duration_ms = round(duration_ms, 2)
        run.finished_at = utcnow()
        run.report = report
        run.model_name = final_state.get("model_name") or settings.llm_model

        INVESTIGATION_DURATION_SECONDS.labels(status=status.value).observe(
            duration_ms / 1000.0
        )
        await db.flush()
        await db.refresh(run, attribute_names=["rca_report", "evidence_items", "agent_results"])
        logger.info(
            "investigation_complete",
            incident_id=str(incident_id),
            investigation_id=str(run.id),
            status=status.value,
            confidence=confidence,
            used_fallback=used_fallback,
            duration_ms=run.duration_ms,
        )
        return run
    except Exception as exc:
        duration_ms = (time.perf_counter() - started) * 1000
        run.status = InvestigationStatus.FAILED
        run.duration_ms = round(duration_ms, 2)
        run.finished_at = utcnow()
        run.report = {"error": str(exc)}
        INVESTIGATION_DURATION_SECONDS.labels(status="failed").observe(
            duration_ms / 1000.0
        )
        await db.flush()
        logger.exception(
            "investigation_failed",
            incident_id=str(incident_id),
            investigation_id=str(run.id),
        )
        raise


async def get_investigation(
    db: AsyncSession, investigation_id: uuid.UUID
) -> InvestigationRun:
    result = await db.execute(
        select(InvestigationRun)
        .options(
            selectinload(InvestigationRun.evidence_items),
            selectinload(InvestigationRun.agent_results),
            selectinload(InvestigationRun.rca_report),
        )
        .where(InvestigationRun.id == investigation_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise InvestigationNotFoundError(investigation_id)
    return run


async def get_latest_for_incident(
    db: AsyncSession, incident_id: uuid.UUID
) -> InvestigationRun | None:
    result = await db.execute(
        select(InvestigationRun)
        .options(
            selectinload(InvestigationRun.evidence_items),
            selectinload(InvestigationRun.agent_results),
            selectinload(InvestigationRun.rca_report),
        )
        .where(InvestigationRun.incident_id == incident_id)
        .order_by(InvestigationRun.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
