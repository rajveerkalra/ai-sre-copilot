"""Context collection REST APIs."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.context import (
    CollectAcceptedResponse,
    CollectRequest,
    CollectorRunResponse,
    InvestigationContextResponse,
)
from app.services import orchestrator
from app.services.orchestrator import ContextNotFoundError, IncidentLookupError

router = APIRouter(prefix="/incidents", tags=["context"])


def _to_response(ctx) -> InvestigationContextResponse:
    runs = [
        CollectorRunResponse.model_validate(r)
        for r in (ctx.collector_runs or [])
    ]
    return InvestigationContextResponse(
        id=ctx.id,
        incident_id=ctx.incident_id,
        status=ctx.status,
        correlation_id=ctx.correlation_id,
        collected_at=ctx.collected_at,
        duration_ms=ctx.duration_ms,
        context=ctx.context or {},
        metrics=ctx.metrics or {},
        logs=ctx.logs or {},
        kubernetes=ctx.kubernetes or {},
        deployment=ctx.deployment or {},
        system=ctx.system or {},
        metadata=ctx.metadata_ or {},
        collector_runs=runs,
        created_at=ctx.created_at,
    )


@router.post("/{incident_id}/collect", response_model=CollectAcceptedResponse)
async def collect_context(
    incident_id: uuid.UUID,
    body: CollectRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> CollectAcceptedResponse:
    body = body or CollectRequest()
    try:
        ctx = await orchestrator.collect_for_incident(
            db,
            incident_id,
            correlation_id=body.correlation_id,
            force=body.force,
        )
    except IncidentLookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CollectAcceptedResponse(
        accepted=True,
        incident_id=incident_id,
        context_id=ctx.id,
        status=ctx.status,
        correlation_id=ctx.correlation_id,
        duration_ms=ctx.duration_ms,
    )


@router.get("/{incident_id}/context", response_model=InvestigationContextResponse)
async def get_context(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> InvestigationContextResponse:
    try:
        ctx = await orchestrator.get_latest_context(db, incident_id)
    except ContextNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_response(ctx)


@router.get("/{incident_id}/metrics")
async def get_metrics(
    incident_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> dict:
    ctx = await _require_ctx(db, incident_id)
    return {
        "incident_id": str(incident_id),
        "status": ctx.status.value,
        "metrics": ctx.metrics,
    }


@router.get("/{incident_id}/logs")
async def get_logs(
    incident_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> dict:
    ctx = await _require_ctx(db, incident_id)
    return {
        "incident_id": str(incident_id),
        "status": ctx.status.value,
        "logs": ctx.logs,
    }


@router.get("/{incident_id}/kubernetes")
async def get_kubernetes(
    incident_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> dict:
    ctx = await _require_ctx(db, incident_id)
    return {
        "incident_id": str(incident_id),
        "status": ctx.status.value,
        "kubernetes": ctx.kubernetes,
    }


@router.get("/{incident_id}/deployment")
async def get_deployment(
    incident_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> dict:
    ctx = await _require_ctx(db, incident_id)
    return {
        "incident_id": str(incident_id),
        "status": ctx.status.value,
        "deployment": ctx.deployment,
    }


@router.get("/{incident_id}/system")
async def get_system(
    incident_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> dict:
    ctx = await _require_ctx(db, incident_id)
    return {
        "incident_id": str(incident_id),
        "status": ctx.status.value,
        "system": ctx.system,
    }


async def _require_ctx(db: AsyncSession, incident_id: uuid.UUID):
    try:
        return await orchestrator.get_latest_context(db, incident_id)
    except ContextNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
