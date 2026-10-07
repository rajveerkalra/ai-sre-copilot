"""Incident lifecycle: create, deduplicate, resolve, notes, timeline."""

from __future__ import annotations

import math
import uuid
from typing import Any

import structlog
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import utcnow
from app.metrics import (
    ALERTS_PROCESSED_TOTAL,
    INCIDENTS_CREATED_TOTAL,
    INCIDENTS_OPEN,
    INCIDENTS_RESOLVED_TOTAL,
    WEBHOOKS_RECEIVED_TOTAL,
)
from app.models import (
    AlertPayload,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    TimelineEvent,
    TimelineEventType,
)
from app.schemas.alertmanager import AlertmanagerWebhook, ParsedAlert
from app.schemas.incident import (
    IncidentListResponse,
    IncidentResponse,
    TimelineEventResponse,
    WebhookIngestResponse,
    WebhookProcessResult,
)
from app.services.fingerprint import (
    fingerprint_for_parsed,
    parse_alert,
    severity_from_label,
)

logger = structlog.get_logger(__name__)


class IncidentNotFoundError(Exception):
    def __init__(self, incident_id: uuid.UUID) -> None:
        self.incident_id = incident_id
        super().__init__(f"Incident {incident_id} not found")


class IncidentAlreadyResolvedError(Exception):
    def __init__(self, incident_id: uuid.UUID) -> None:
        self.incident_id = incident_id
        super().__init__(f"Incident {incident_id} is already resolved")


def _to_severity(value: str) -> IncidentSeverity:
    try:
        return IncidentSeverity(severity_from_label(value))
    except ValueError:
        return IncidentSeverity.UNKNOWN


def _timeline_response(event: TimelineEvent) -> TimelineEventResponse:
    return TimelineEventResponse(
        id=event.id,
        event_type=event.event_type,
        message=event.message,
        metadata=event.metadata_ or {},
        created_at=event.created_at,
    )


async def refresh_open_gauge(db: AsyncSession) -> None:
    result = await db.execute(
        select(func.count())
        .select_from(Incident)
        .where(Incident.status == IncidentStatus.OPEN)
    )
    INCIDENTS_OPEN.set(int(result.scalar_one()))


async def ingest_alertmanager_webhook(
    db: AsyncSession,
    payload: AlertmanagerWebhook,
) -> WebhookIngestResponse:
    WEBHOOKS_RECEIVED_TOTAL.labels(status=payload.status or "unknown").inc()
    results: list[WebhookProcessResult] = []

    for alert in payload.alerts:
        parsed = parse_alert(alert)
        result = await _process_parsed_alert(db, parsed, payload)
        results.append(result)

    await refresh_open_gauge(db)
    await db.flush()

    logger.info(
        "webhook_ingested",
        alert_count=len(payload.alerts),
        webhook_status=payload.status,
        actions=[r.action for r in results],
    )
    return WebhookIngestResponse(
        accepted=True,
        alert_count=len(payload.alerts),
        results=results,
    )


async def _process_parsed_alert(
    db: AsyncSession,
    parsed: ParsedAlert,
    webhook: AlertmanagerWebhook,
) -> WebhookProcessResult:
    fingerprint = fingerprint_for_parsed(parsed)
    severity = _to_severity(parsed.severity)

    if parsed.status == "resolved":
        return await _handle_resolved_alert(db, parsed, fingerprint, webhook)

    open_incident = await _find_open_by_fingerprint(db, fingerprint)
    if open_incident is None:
        incident = await _create_incident(db, parsed, fingerprint, severity, webhook)
        ALERTS_PROCESSED_TOTAL.labels(action="created", severity=severity.value).inc()
        return WebhookProcessResult(
            incident_id=incident.id,
            fingerprint=fingerprint,
            action="created",
            occurrence_count=incident.occurrence_count,
            alertname=parsed.alertname,
            title=incident.title,
            severity=incident.severity.value,
            service=incident.service or "",
        )

    incident = await _deduplicate_alert(db, open_incident, parsed, webhook)
    ALERTS_PROCESSED_TOTAL.labels(
        action="deduplicated", severity=severity.value
    ).inc()
    return WebhookProcessResult(
        incident_id=incident.id,
        fingerprint=fingerprint,
        action="deduplicated",
        occurrence_count=incident.occurrence_count,
        alertname=parsed.alertname,
    )


async def _find_open_by_fingerprint(
    db: AsyncSession, fingerprint: str
) -> Incident | None:
    stmt = (
        select(Incident)
        .where(
            Incident.fingerprint == fingerprint,
            Incident.status == IncidentStatus.OPEN,
        )
        .with_for_update()
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _create_incident(
    db: AsyncSession,
    parsed: ParsedAlert,
    fingerprint: str,
    severity: IncidentSeverity,
    webhook: AlertmanagerWebhook,
) -> Incident:
    now = utcnow()
    incident = Incident(
        title=parsed.title,
        status=IncidentStatus.OPEN,
        severity=severity,
        fingerprint=fingerprint,
        occurrence_count=1,
        alertname=parsed.alertname,
        service=parsed.service or None,
        namespace=parsed.namespace or None,
        created_at=now,
        updated_at=now,
    )
    db.add(incident)
    await db.flush()

    db.add(
        TimelineEvent(
            incident_id=incident.id,
            event_type=TimelineEventType.INCIDENT_CREATED,
            message=f"Incident created from {parsed.alertname} alert",
            metadata_={
                "alertname": parsed.alertname,
                "severity": severity.value,
                "fingerprint": fingerprint,
                "labels": parsed.labels,
                "annotations": parsed.annotations,
            },
        )
    )
    db.add(
        TimelineEvent(
            incident_id=incident.id,
            event_type=TimelineEventType.ALERT_RECEIVED,
            message=f"Alert received: {parsed.alertname}",
            metadata_={
                "alert": parsed.model_dump(mode="json"),
                "webhook_status": webhook.status,
                "receiver": webhook.receiver,
            },
        )
    )
    db.add(
        AlertPayload(
            incident_id=incident.id,
            raw_payload=webhook.model_dump(mode="json"),
            received_at=now,
        )
    )
    db.add(
        TimelineEvent(
            incident_id=incident.id,
            event_type=TimelineEventType.CONTEXT_COLLECTION_TRIGGERED,
            message="Context collection scheduled for investigation evidence",
            metadata_={"phase": 3, "target": "context-service"},
        )
    )

    INCIDENTS_CREATED_TOTAL.labels(severity=severity.value).inc()
    logger.info(
        "incident_created",
        incident_id=str(incident.id),
        fingerprint=fingerprint,
        alertname=parsed.alertname,
        severity=severity.value,
    )
    return incident


async def _deduplicate_alert(
    db: AsyncSession,
    incident: Incident,
    parsed: ParsedAlert,
    webhook: AlertmanagerWebhook,
) -> Incident:
    now = utcnow()
    incident.occurrence_count += 1
    incident.updated_at = now
    # Escalate severity if a more severe alert arrives
    new_severity = _to_severity(parsed.severity)
    if _severity_rank(new_severity) > _severity_rank(incident.severity):
        incident.severity = new_severity
        db.add(
            TimelineEvent(
                incident_id=incident.id,
                event_type=TimelineEventType.INCIDENT_UPDATED,
                message=f"Severity escalated to {new_severity.value}",
                metadata_={"severity": new_severity.value},
            )
        )

    db.add(
        TimelineEvent(
            incident_id=incident.id,
            event_type=TimelineEventType.ALERT_REPEATED,
            message="Alert repeated",
            metadata_={
                "occurrence_count": incident.occurrence_count,
                "alertname": parsed.alertname,
                "labels": parsed.labels,
            },
        )
    )
    db.add(
        AlertPayload(
            incident_id=incident.id,
            raw_payload=webhook.model_dump(mode="json"),
            received_at=now,
        )
    )
    await db.flush()
    logger.info(
        "incident_deduplicated",
        incident_id=str(incident.id),
        occurrence_count=incident.occurrence_count,
        fingerprint=incident.fingerprint,
    )
    return incident


async def _handle_resolved_alert(
    db: AsyncSession,
    parsed: ParsedAlert,
    fingerprint: str,
    webhook: AlertmanagerWebhook,
) -> WebhookProcessResult:
    open_incident = await _find_open_by_fingerprint(db, fingerprint)
    if open_incident is None:
        # No open incident to resolve — ignore quietly but acknowledge
        logger.info(
            "resolved_alert_without_open_incident",
            fingerprint=fingerprint,
            alertname=parsed.alertname,
        )
        ALERTS_PROCESSED_TOTAL.labels(
            action="resolved_noop", severity=parsed.severity
        ).inc()
        # Create a synthetic result referencing a nil UUID is awkward;
        # instead create a transient resolved marker only if we find any
        # historical incident — otherwise return a zero UUID with action.
        historical = await db.execute(
            select(Incident)
            .where(Incident.fingerprint == fingerprint)
            .order_by(Incident.created_at.desc())
            .limit(1)
        )
        existing = historical.scalar_one_or_none()
        if existing is None:
            # Still accept the webhook; invent a no-op using a nil-like placeholder
            # by creating nothing — return fingerprint only via a dummy resolved row.
            # Prefer: return last-known id if any; else create ephemeral noop id.
            noop_id = uuid.UUID(int=0)
            return WebhookProcessResult(
                incident_id=noop_id,
                fingerprint=fingerprint,
                action="resolved_noop",
                occurrence_count=0,
                alertname=parsed.alertname,
            )
        return WebhookProcessResult(
            incident_id=existing.id,
            fingerprint=fingerprint,
            action="resolved_noop",
            occurrence_count=existing.occurrence_count,
            alertname=parsed.alertname,
        )

    await _resolve_incident(
        db,
        open_incident,
        message=f"Resolved via Alertmanager for {parsed.alertname}",
        source="alertmanager",
        metadata={
            "alert": parsed.model_dump(mode="json"),
            "webhook_status": webhook.status,
        },
    )
    db.add(
        AlertPayload(
            incident_id=open_incident.id,
            raw_payload=webhook.model_dump(mode="json"),
            received_at=utcnow(),
        )
    )
    ALERTS_PROCESSED_TOTAL.labels(
        action="resolved", severity=parsed.severity
    ).inc()
    return WebhookProcessResult(
        incident_id=open_incident.id,
        fingerprint=fingerprint,
        action="resolved",
        occurrence_count=open_incident.occurrence_count,
        alertname=parsed.alertname,
    )


def _severity_rank(severity: IncidentSeverity) -> int:
    order = {
        IncidentSeverity.UNKNOWN: 0,
        IncidentSeverity.INFO: 1,
        IncidentSeverity.WARNING: 2,
        IncidentSeverity.CRITICAL: 3,
    }
    return order.get(severity, 0)


async def _resolve_incident(
    db: AsyncSession,
    incident: Incident,
    *,
    message: str,
    source: str,
    metadata: dict[str, Any] | None = None,
) -> Incident:
    if incident.status == IncidentStatus.RESOLVED:
        raise IncidentAlreadyResolvedError(incident.id)

    now = utcnow()
    incident.status = IncidentStatus.RESOLVED
    incident.resolved_at = now
    incident.updated_at = now
    db.add(
        TimelineEvent(
            incident_id=incident.id,
            event_type=TimelineEventType.INCIDENT_RESOLVED,
            message=message,
            metadata_={"source": source, **(metadata or {})},
        )
    )
    await db.flush()
    INCIDENTS_RESOLVED_TOTAL.labels(source=source).inc()
    logger.info(
        "incident_resolved",
        incident_id=str(incident.id),
        source=source,
    )
    return incident


async def list_incidents(
    db: AsyncSession,
    *,
    status: IncidentStatus | None = None,
    severity: IncidentSeverity | None = None,
    page: int = 1,
    page_size: int = 20,
) -> IncidentListResponse:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)

    filters = []
    if status is not None:
        filters.append(Incident.status == status)
    if severity is not None:
        filters.append(Incident.severity == severity)

    count_stmt: Select[Any] = select(func.count()).select_from(Incident)
    list_stmt: Select[Any] = select(Incident).order_by(Incident.created_at.desc())
    for f in filters:
        count_stmt = count_stmt.where(f)
        list_stmt = list_stmt.where(f)

    total = int((await db.execute(count_stmt)).scalar_one())
    offset = (page - 1) * page_size
    rows = (
        await db.execute(list_stmt.offset(offset).limit(page_size))
    ).scalars().all()

    pages = max(1, math.ceil(total / page_size)) if total else 0
    return IncidentListResponse(
        items=[IncidentResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


async def get_incident(db: AsyncSession, incident_id: uuid.UUID) -> Incident:
    result = await db.execute(
        select(Incident)
        .options(selectinload(Incident.timeline_events))
        .where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if incident is None:
        raise IncidentNotFoundError(incident_id)
    return incident


async def get_timeline(
    db: AsyncSession, incident_id: uuid.UUID
) -> list[TimelineEventResponse]:
    # Ensure incident exists
    exists = await db.execute(select(Incident.id).where(Incident.id == incident_id))
    if exists.scalar_one_or_none() is None:
        raise IncidentNotFoundError(incident_id)

    result = await db.execute(
        select(TimelineEvent)
        .where(TimelineEvent.incident_id == incident_id)
        .order_by(TimelineEvent.created_at.asc())
    )
    events = result.scalars().all()
    return [_timeline_response(e) for e in events]


async def resolve_incident(
    db: AsyncSession,
    incident_id: uuid.UUID,
    *,
    message: str | None = None,
) -> Incident:
    incident = await get_incident(db, incident_id)
    await _resolve_incident(
        db,
        incident,
        message=message or "Incident resolved by operator",
        source="api",
    )
    await refresh_open_gauge(db)
    return incident


async def add_note(
    db: AsyncSession,
    incident_id: uuid.UUID,
    message: str,
) -> TimelineEvent:
    incident = await get_incident(db, incident_id)
    incident.updated_at = utcnow()
    event = TimelineEvent(
        incident_id=incident.id,
        event_type=TimelineEventType.NOTE_ADDED,
        message=message,
        metadata_={"source": "api"},
    )
    db.add(event)
    await db.flush()
    logger.info("note_added", incident_id=str(incident_id))
    return event


async def add_timeline_event(
    db: AsyncSession,
    incident_id: uuid.UUID,
    *,
    event_type: TimelineEventType,
    message: str,
    metadata: dict | None = None,
) -> TimelineEvent:
    """Append a typed timeline event (used by remediation-service and peers)."""
    incident = await get_incident(db, incident_id)
    incident.updated_at = utcnow()
    event = TimelineEvent(
        incident_id=incident.id,
        event_type=event_type,
        message=message,
        metadata_=metadata or {"source": "api"},
    )
    db.add(event)
    await db.flush()
    logger.info(
        "timeline_event_added",
        incident_id=str(incident_id),
        event_type=event_type.value,
    )
    return event
