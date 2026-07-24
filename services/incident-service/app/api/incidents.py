"""Incident REST API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import require_read, require_write
from app.models import IncidentSeverity, IncidentStatus
from app.schemas.incident import (
    IncidentDetailResponse,
    IncidentListResponse,
    IncidentResponse,
    NoteCreateRequest,
    ResolveRequest,
    TimelineEventCreateRequest,
    TimelineEventResponse,
)
from app.services import incident_service
from app.services.incident_service import (
    IncidentAlreadyResolvedError,
    IncidentNotFoundError,
)
from libs.common.audit import emit_audit
from libs.common.auth import Principal

router = APIRouter(prefix="/incidents", tags=["incidents"])
v1_router = APIRouter(prefix="/api/v1/incidents", tags=["incidents-v1"])


@router.get("", response_model=IncidentListResponse)
@v1_router.get("", response_model=IncidentListResponse)
async def list_incidents(
    status_filter: IncidentStatus | None = Query(None, alias="status"),
    severity: IncidentSeverity | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_read),
) -> IncidentListResponse:
    return await incident_service.list_incidents(
        db,
        status=status_filter,
        severity=severity,
        page=page,
        page_size=page_size,
    )


@router.get("/{incident_id}", response_model=IncidentDetailResponse)
@v1_router.get("/{incident_id}", response_model=IncidentDetailResponse)
async def get_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_read),
) -> IncidentDetailResponse:
    try:
        incident = await incident_service.get_incident(db, incident_id)
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    timeline = [
        TimelineEventResponse(
            id=e.id,
            event_type=e.event_type,
            message=e.message,
            metadata=e.metadata_ or {},
            created_at=e.created_at,
        )
        for e in incident.timeline_events
    ]
    base = IncidentResponse.model_validate(incident)
    return IncidentDetailResponse(**base.model_dump(), timeline=timeline)


@router.get("/{incident_id}/timeline", response_model=list[TimelineEventResponse])
@v1_router.get("/{incident_id}/timeline", response_model=list[TimelineEventResponse])
async def get_timeline(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_read),
) -> list[TimelineEventResponse]:
    try:
        return await incident_service.get_timeline(db, incident_id)
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{incident_id}/resolve", response_model=IncidentResponse)
@v1_router.post("/{incident_id}/resolve", response_model=IncidentResponse)
async def resolve_incident(
    incident_id: uuid.UUID,
    body: ResolveRequest | None = None,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_write),
) -> IncidentResponse:
    body = body or ResolveRequest()
    try:
        incident = await incident_service.resolve_incident(
            db, incident_id, message=body.message
        )
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IncidentAlreadyResolvedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    emit_audit(
        action="incident.resolve",
        actor=principal.sub,
        resource_type="incident",
        resource_id=str(incident_id),
        service="incident-service",
    )
    return IncidentResponse.model_validate(incident)


@router.post(
    "/{incident_id}/notes",
    response_model=TimelineEventResponse,
    status_code=status.HTTP_201_CREATED,
)
@v1_router.post(
    "/{incident_id}/notes",
    response_model=TimelineEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_note(
    incident_id: uuid.UUID,
    body: NoteCreateRequest,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_write),
) -> TimelineEventResponse:
    try:
        event = await incident_service.add_note(db, incident_id, body.message)
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    emit_audit(
        action="incident.note",
        actor=principal.sub,
        resource_type="incident",
        resource_id=str(incident_id),
        service="incident-service",
    )
    return TimelineEventResponse(
        id=event.id,
        event_type=event.event_type,
        message=event.message,
        metadata=event.metadata_ or {},
        created_at=event.created_at,
    )


@router.post(
    "/{incident_id}/timeline-events",
    response_model=TimelineEventResponse,
    status_code=status.HTTP_201_CREATED,
)
@v1_router.post(
    "/{incident_id}/timeline-events",
    response_model=TimelineEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_timeline_event(
    incident_id: uuid.UUID,
    body: TimelineEventCreateRequest,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_write),
) -> TimelineEventResponse:
    """Typed timeline events for peer services (e.g. remediation-service)."""
    try:
        event = await incident_service.add_timeline_event(
            db,
            incident_id,
            event_type=body.event_type,
            message=body.message,
            metadata=body.metadata,
        )
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TimelineEventResponse(
        id=event.id,
        event_type=event.event_type,
        message=event.message,
        metadata=event.metadata_ or {},
        created_at=event.created_at,
    )
