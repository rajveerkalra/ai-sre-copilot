"""Remediation orchestration."""

from __future__ import annotations

import time
import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import utcnow
from app.metrics import (
    REMEDIATION_APPROVALS_TOTAL,
    REMEDIATION_DURATION_SECONDS,
    REMEDIATION_EXECUTIONS_TOTAL,
    REMEDIATION_PROPOSALS_TOTAL,
)
from app.models import (
    ApprovalDecision,
    ProposalStatus,
    RemediationApproval,
    RemediationAuditLog,
    RemediationExecution,
    RemediationProposal,
)
from app.services import clients
from app.services.executor import ExecutionError, execute_proposal, resolve_dry_run
from app.services.mapper import map_rca_to_proposals

logger = structlog.get_logger(__name__)


class RemediationNotFoundError(Exception):
    def __init__(self, remediation_id: uuid.UUID) -> None:
        super().__init__(f"Remediation {remediation_id} not found")
        self.remediation_id = remediation_id


class InvalidStateError(Exception):
    pass


async def _audit(
    db: AsyncSession,
    *,
    event_type: str,
    message: str,
    actor: str = "system",
    proposal_id: uuid.UUID | None = None,
    incident_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        RemediationAuditLog(
            proposal_id=proposal_id,
            incident_id=incident_id,
            event_type=event_type,
            actor=actor,
            message=message,
            details=details or {},
            created_at=utcnow(),
        )
    )


async def propose_for_incident(
    db: AsyncSession, incident_id: uuid.UUID
) -> list[RemediationProposal]:
    inv = await clients.fetch_latest_investigation(incident_id)
    investigation_id = uuid.UUID(str(inv["id"]))
    rca = await clients.fetch_rca(investigation_id)
    mapped = map_rca_to_proposals(
        incident_id=incident_id,
        investigation_id=investigation_id,
        rca=rca,
    )
    created: list[RemediationProposal] = []
    for item in mapped:
        prop = RemediationProposal(
            incident_id=item["incident_id"],
            investigation_id=item["investigation_id"],
            action_type=item["action_type"],
            title=item["title"],
            rationale=item["rationale"],
            parameters=item["parameters"],
            confidence=item["confidence"],
            risk_level=item["risk_level"],
            requires_dry_run_default=item["requires_dry_run_default"],
            status=ProposalStatus.PROPOSED,
            evidence_ids=item["evidence_ids"],
            root_cause=item["root_cause"],
        )
        db.add(prop)
        await db.flush()
        REMEDIATION_PROPOSALS_TOTAL.labels(action_type=prop.action_type.value).inc()
        await _audit(
            db,
            event_type="proposed",
            message=prop.title,
            proposal_id=prop.id,
            incident_id=incident_id,
            details={"action_type": prop.action_type.value, "confidence": prop.confidence},
        )
        created.append(prop)

    await clients.post_timeline_event(
        incident_id,
        event_type="remediation_proposed",
        message=f"Proposed {len(created)} remediation action(s)",
        metadata={
            "count": len(created),
            "proposal_ids": [str(p.id) for p in created],
            "source": "remediation-service",
        },
    )
    await db.flush()
    logger.info(
        "remediations_proposed",
        incident_id=str(incident_id),
        count=len(created),
    )
    return created


async def list_for_incident(
    db: AsyncSession, incident_id: uuid.UUID
) -> list[RemediationProposal]:
    result = await db.execute(
        select(RemediationProposal)
        .options(
            selectinload(RemediationProposal.approvals),
            selectinload(RemediationProposal.executions),
        )
        .where(RemediationProposal.incident_id == incident_id)
        .order_by(RemediationProposal.created_at.desc())
    )
    return list(result.scalars().all())


async def list_pending(db: AsyncSession) -> list[RemediationProposal]:
    result = await db.execute(
        select(RemediationProposal)
        .options(
            selectinload(RemediationProposal.approvals),
            selectinload(RemediationProposal.executions),
        )
        .where(RemediationProposal.status == ProposalStatus.PROPOSED)
        .order_by(RemediationProposal.created_at.asc())
    )
    return list(result.scalars().all())


async def get_proposal(db: AsyncSession, proposal_id: uuid.UUID) -> RemediationProposal:
    result = await db.execute(
        select(RemediationProposal)
        .options(
            selectinload(RemediationProposal.approvals),
            selectinload(RemediationProposal.executions),
        )
        .where(RemediationProposal.id == proposal_id)
    )
    prop = result.scalar_one_or_none()
    if prop is None:
        raise RemediationNotFoundError(proposal_id)
    return prop


async def approve(
    db: AsyncSession,
    proposal_id: uuid.UUID,
    *,
    approved_by: str,
    comment: str = "",
) -> RemediationProposal:
    prop = await get_proposal(db, proposal_id)
    if prop.status != ProposalStatus.PROPOSED:
        raise InvalidStateError(f"Cannot approve in status {prop.status.value}")
    prop.status = ProposalStatus.APPROVED
    db.add(
        RemediationApproval(
            proposal_id=prop.id,
            decision=ApprovalDecision.APPROVED,
            actor=approved_by,
            comment=comment,
            created_at=utcnow(),
        )
    )
    REMEDIATION_APPROVALS_TOTAL.labels(decision="approved").inc()
    await _audit(
        db,
        event_type="approved",
        message=f"Approved by {approved_by}",
        actor=approved_by,
        proposal_id=prop.id,
        incident_id=prop.incident_id,
        details={"comment": comment},
    )
    await clients.post_timeline_event(
        prop.incident_id,
        event_type="remediation_approved",
        message=f"Remediation approved: {prop.title}",
        metadata={
            "proposal_id": str(prop.id),
            "approved_by": approved_by,
            "action_type": prop.action_type.value,
            "source": "remediation-service",
        },
    )
    await db.flush()
    return prop


async def reject(
    db: AsyncSession,
    proposal_id: uuid.UUID,
    *,
    rejected_by: str,
    comment: str = "",
) -> RemediationProposal:
    prop = await get_proposal(db, proposal_id)
    if prop.status != ProposalStatus.PROPOSED:
        raise InvalidStateError(f"Cannot reject in status {prop.status.value}")
    prop.status = ProposalStatus.REJECTED
    db.add(
        RemediationApproval(
            proposal_id=prop.id,
            decision=ApprovalDecision.REJECTED,
            actor=rejected_by,
            comment=comment,
            created_at=utcnow(),
        )
    )
    REMEDIATION_APPROVALS_TOTAL.labels(decision="rejected").inc()
    await _audit(
        db,
        event_type="rejected",
        message=f"Rejected by {rejected_by}",
        actor=rejected_by,
        proposal_id=prop.id,
        incident_id=prop.incident_id,
        details={"comment": comment},
    )
    await clients.post_timeline_event(
        prop.incident_id,
        event_type="remediation_rejected",
        message=f"Remediation rejected: {prop.title}",
        metadata={
            "proposal_id": str(prop.id),
            "rejected_by": rejected_by,
            "action_type": prop.action_type.value,
            "source": "remediation-service",
        },
    )
    await db.flush()
    return prop


async def execute(
    db: AsyncSession,
    proposal_id: uuid.UUID,
    *,
    dry_run: bool | None = None,
    actor: str = "operator",
) -> RemediationExecution:
    prop = await get_proposal(db, proposal_id)
    if prop.status == ProposalStatus.SUCCEEDED:
        raise InvalidStateError("Already executed successfully")
    if prop.status != ProposalStatus.APPROVED:
        raise InvalidStateError(
            f"Execute requires status=approved (got {prop.status.value})"
        )

    effective_dry = resolve_dry_run(prop, requested_dry_run=dry_run)
    prop.status = ProposalStatus.EXECUTING
    await db.flush()

    started = time.perf_counter()
    execution = RemediationExecution(
        proposal_id=prop.id,
        dry_run=effective_dry,
        status="running",
        result={},
        started_at=utcnow(),
    )
    db.add(execution)
    await db.flush()

    try:
        result = await execute_proposal(prop, dry_run=effective_dry)
        duration = time.perf_counter() - started
        execution.status = "succeeded"
        execution.result = result
        execution.finished_at = utcnow()
        execution.duration_ms = round(duration * 1000, 2)
        prop.status = ProposalStatus.SUCCEEDED
        REMEDIATION_EXECUTIONS_TOTAL.labels(
            status="succeeded",
            dry_run=str(effective_dry).lower(),
            action_type=prop.action_type.value,
        ).inc()
        REMEDIATION_DURATION_SECONDS.labels(
            action_type=prop.action_type.value,
            dry_run=str(effective_dry).lower(),
        ).observe(duration)
        await _audit(
            db,
            event_type="executed",
            message=f"Executed ({'dry-run' if effective_dry else 'live'})",
            actor=actor,
            proposal_id=prop.id,
            incident_id=prop.incident_id,
            details=result,
        )
        await clients.post_timeline_event(
            prop.incident_id,
            event_type="remediation_executed",
            message=f"Remediation executed: {prop.title}",
            metadata={
                "proposal_id": str(prop.id),
                "dry_run": effective_dry,
                "action_type": prop.action_type.value,
                "source": "remediation-service",
            },
        )
    except Exception as exc:
        duration = time.perf_counter() - started
        execution.status = "failed"
        execution.error = str(exc)
        execution.finished_at = utcnow()
        execution.duration_ms = round(duration * 1000, 2)
        prop.status = ProposalStatus.FAILED
        REMEDIATION_EXECUTIONS_TOTAL.labels(
            status="failed",
            dry_run=str(effective_dry).lower(),
            action_type=prop.action_type.value,
        ).inc()
        await _audit(
            db,
            event_type="execution_failed",
            message=str(exc),
            actor=actor,
            proposal_id=prop.id,
            incident_id=prop.incident_id,
        )
        await db.flush()
        if isinstance(exc, ExecutionError):
            raise InvalidStateError(str(exc)) from exc
        raise

    await db.flush()
    return execution
