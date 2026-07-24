"""Remediation REST APIs."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import check_db, get_db
from app.deps import (
    get_principal,
    rate_limit_mutate,
    require_approve,
    require_execute,
    require_propose,
    require_read,
)
from app.schemas.remediation import (
    ApproveRequest,
    ExecuteRequest,
    ExecutionResponse,
    ProposeResponse,
    ProposalResponse,
    RejectRequest,
)
from app.services import orchestrator
from app.services.clients import UpstreamError
from app.services.orchestrator import InvalidStateError, RemediationNotFoundError
from libs.common.audit import emit_audit
from libs.common.auth import Principal

router = APIRouter(tags=["remediation"])
v1 = APIRouter(prefix="/api/v1", tags=["remediation-v1"])


async def propose(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_propose),
) -> ProposeResponse:
    try:
        props = await orchestrator.propose_for_incident(db, incident_id)
    except UpstreamError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    emit_audit(
        action="remediation.propose",
        actor=principal.sub,
        resource_type="incident",
        resource_id=str(incident_id),
        detail={"count": len(props)},
        service="remediation-service",
    )
    return ProposeResponse(
        incident_id=incident_id,
        count=len(props),
        proposals=[ProposalResponse.model_validate(p) for p in props],
    )


async def list_for_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_read),
) -> list[ProposalResponse]:
    props = await orchestrator.list_for_incident(db, incident_id)
    return [ProposalResponse.model_validate(p) for p in props]


async def pending(
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_read),
) -> list[ProposalResponse]:
    props = await orchestrator.list_pending(db)
    return [ProposalResponse.model_validate(p) for p in props]


async def get_one(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_read),
) -> ProposalResponse:
    try:
        prop = await orchestrator.get_proposal(db, proposal_id)
    except RemediationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProposalResponse.model_validate(prop)


async def approve(
    proposal_id: uuid.UUID,
    body: ApproveRequest,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_approve),
    __: None = Depends(rate_limit_mutate),
) -> ProposalResponse:
    approved_by = body.approved_by or principal.sub
    try:
        prop = await orchestrator.approve(
            db, proposal_id, approved_by=approved_by, comment=body.comment
        )
    except RemediationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    emit_audit(
        action="remediation.approve",
        actor=principal.sub,
        resource_type="remediation",
        resource_id=str(proposal_id),
        detail={"approved_by": approved_by},
        service="remediation-service",
    )
    return ProposalResponse.model_validate(prop)


async def reject(
    proposal_id: uuid.UUID,
    body: RejectRequest,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_approve),
    __: None = Depends(rate_limit_mutate),
) -> ProposalResponse:
    rejected_by = body.rejected_by or principal.sub
    try:
        prop = await orchestrator.reject(
            db, proposal_id, rejected_by=rejected_by, comment=body.comment
        )
    except RemediationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    emit_audit(
        action="remediation.reject",
        actor=principal.sub,
        resource_type="remediation",
        resource_id=str(proposal_id),
        detail={"rejected_by": rejected_by},
        service="remediation-service",
    )
    return ProposalResponse.model_validate(prop)


async def execute(
    proposal_id: uuid.UUID,
    body: ExecuteRequest | None = None,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_execute),
    __: None = Depends(rate_limit_mutate),
) -> ExecutionResponse:
    body = body or ExecuteRequest()
    actor = body.actor or principal.sub
    try:
        execution = await orchestrator.execute(
            db, proposal_id, dry_run=body.dry_run, actor=actor
        )
    except RemediationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    emit_audit(
        action="remediation.execute",
        actor=principal.sub,
        resource_type="remediation",
        resource_id=str(proposal_id),
        outcome="success" if execution.status == "succeeded" else execution.status,
        detail={"dry_run": execution.dry_run, "status": execution.status},
        service="remediation-service",
    )
    return ExecutionResponse.model_validate(execution)


# Legacy + versioned mounts
for r in (router, v1):
    r.add_api_route(
        "/incidents/{incident_id}/remediations/propose",
        propose,
        methods=["POST"],
        response_model=ProposeResponse,
    )
    r.add_api_route(
        "/incidents/{incident_id}/remediations",
        list_for_incident,
        methods=["GET"],
        response_model=list[ProposalResponse],
    )
    r.add_api_route(
        "/remediations/pending",
        pending,
        methods=["GET"],
        response_model=list[ProposalResponse],
    )
    r.add_api_route(
        "/remediations/{proposal_id}",
        get_one,
        methods=["GET"],
        response_model=ProposalResponse,
    )
    r.add_api_route(
        "/remediations/{proposal_id}/approve",
        approve,
        methods=["POST"],
        response_model=ProposalResponse,
    )
    r.add_api_route(
        "/remediations/{proposal_id}/reject",
        reject,
        methods=["POST"],
        response_model=ProposalResponse,
    )
    r.add_api_route(
        "/remediations/{proposal_id}/execute",
        execute,
        methods=["POST"],
        response_model=ExecutionResponse,
    )


@router.get("/health")
@router.get("/healthz")
async def health() -> dict:
    from app import __version__
    from app.config import get_settings

    s = get_settings()
    return {"status": "healthy", "service": s.service_name, "version": __version__}


@router.get("/ready")
@router.get("/readyz")
async def ready():
    from app.config import get_settings

    settings = get_settings()
    try:
        await check_db()
        return {"status": "healthy", "service": settings.service_name, "db": "ok"}
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": settings.service_name,
                "db": "error",
                "detail": str(exc),
            },
        )
