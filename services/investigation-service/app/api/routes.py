"""Investigation REST APIs."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import check_db, get_db
from app.schemas.investigation import (
    FeedbackRequest,
    FeedbackResponse,
    InvestigateRequest,
    InvestigateResponse,
    InvestigationDetail,
)
from app.services import feedback as feedback_service
from app.services import orchestrator
from app.services.feedback import NoRcaError
from app.services.orchestrator import (
    ContextMissingError,
    InvestigationNotFoundError,
)

router = APIRouter(tags=["investigation"])


@router.post("/incidents/{incident_id}/investigate", response_model=InvestigateResponse)
async def investigate(
    incident_id: uuid.UUID,
    body: InvestigateRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> InvestigateResponse:
    body = body or InvestigateRequest()
    try:
        run = await orchestrator.run_investigation(
            db, incident_id, correlation_id=body.correlation_id
        )
    except ContextMissingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Investigation failed: {exc}"
        ) from exc

    root_cause = None
    if run.rca_report is not None:
        root_cause = run.rca_report.root_cause
    elif run.report:
        root_cause = run.report.get("root_cause")

    return InvestigateResponse(
        accepted=True,
        investigation_id=run.id,
        incident_id=incident_id,
        status=run.status,
        confidence=run.confidence,
        used_fallback=run.used_fallback,
        duration_ms=run.duration_ms,
        root_cause=root_cause,
    )


@router.get("/investigations/{investigation_id}", response_model=InvestigationDetail)
async def get_investigation(
    investigation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> InvestigationDetail:
    try:
        run = await orchestrator.get_investigation(db, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return InvestigationDetail.model_validate(run)


@router.get("/investigations/{investigation_id}/evidence")
async def get_evidence(
    investigation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        run = await orchestrator.get_investigation(db, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "investigation_id": str(investigation_id),
        "count": len(run.evidence_items),
        "evidence": [
            {
                "evidence_id": e.evidence_id,
                "source": e.source,
                "summary": e.summary,
                "raw": e.raw,
            }
            for e in run.evidence_items
        ],
    }


@router.get("/investigations/{investigation_id}/rca")
async def get_rca(
    investigation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        run = await orchestrator.get_investigation(db, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if run.rca_report is None:
        raise HTTPException(status_code=404, detail="RCA not available")
    rca = run.rca_report
    return {
        "investigation_id": str(investigation_id),
        "root_cause": rca.root_cause,
        "confidence": rca.confidence,
        "business_impact": rca.business_impact,
        "next_steps": rca.next_steps,
        "evidence_ids": rca.evidence_ids,
        "unknowns": rca.unknowns,
        "supporting_runbooks": rca.supporting_runbooks,
        "used_fallback": rca.used_fallback,
        "full_report": rca.full_report,
        "feedback_status": rca.feedback_status,
        "feedback_notes": rca.feedback_notes,
        "learned_doc_id": rca.learned_doc_id,
    }


@router.post("/investigations/{investigation_id}/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    investigation_id: uuid.UUID,
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """Operator verdict on an RCA. A "correct" verdict feeds the RCA and its
    grounding evidence back into the knowledge-service as a new citable
    precedent for future investigations -- see app/services/feedback.py."""
    try:
        rca = await feedback_service.submit_feedback(
            db,
            investigation_id,
            status=body.status,
            notes=body.notes,
            reviewed_by=body.reviewed_by,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoRcaError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return FeedbackResponse.model_validate(rca)


@router.get("/incidents/{incident_id}/investigation")
async def latest_for_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    run = await orchestrator.get_latest_for_incident(db, incident_id)
    if run is None:
        raise HTTPException(status_code=404, detail="No investigation for incident")
    return InvestigationDetail.model_validate(run).model_dump(mode="json")


@router.get("/health")
@router.get("/healthz")
async def health() -> dict:
    from app import __version__
    from app.config import get_settings

    s = get_settings()
    return {"status": "healthy", "service": s.service_name, "version": __version__}


@router.get("/live")
@router.get("/livez")
async def live() -> dict:
    from app.config import get_settings

    return {"status": "healthy", "service": get_settings().service_name}


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
