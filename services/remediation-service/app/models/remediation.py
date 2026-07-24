"""Remediation ORM models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow

JSONType = JSON().with_variant(JSONB(), "postgresql")


class ActionType(str, enum.Enum):
    CLEAR_FAULT = "clear_fault"
    RESTART_SERVICE = "restart_service"
    SCALE = "scale"
    ROLLBACK = "rollback"
    RUNBOOK_MANUAL = "runbook_manual"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProposalStatus(str, enum.Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalDecision(str, enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class RemediationProposal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "remediation_proposals"
    __table_args__ = (
        Index("ix_remediation_proposals_incident_id", "incident_id"),
        Index("ix_remediation_proposals_status", "status"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    investigation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    action_type: Mapped[ActionType] = mapped_column(
        Enum(
            ActionType,
            name="remediation_action_type",
            values_callable=lambda e: [x.value for x in e],
            native_enum=False,
            length=32,
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(
            RiskLevel,
            name="remediation_risk_level",
            values_callable=lambda e: [x.value for x in e],
            native_enum=False,
            length=16,
        ),
        nullable=False,
        default=RiskLevel.MEDIUM,
    )
    requires_dry_run_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    status: Mapped[ProposalStatus] = mapped_column(
        Enum(
            ProposalStatus,
            name="remediation_proposal_status",
            values_callable=lambda e: [x.value for x in e],
            native_enum=False,
            length=32,
        ),
        nullable=False,
        default=ProposalStatus.PROPOSED,
    )
    evidence_ids: Mapped[list[Any]] = mapped_column(JSONType, nullable=False, default=list)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False, default="")

    approvals: Mapped[list[RemediationApproval]] = relationship(
        back_populates="proposal", cascade="all, delete-orphan"
    )
    executions: Mapped[list[RemediationExecution]] = relationship(
        back_populates="proposal", cascade="all, delete-orphan"
    )


class RemediationApproval(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "remediation_approvals"
    __table_args__ = (Index("ix_remediation_approvals_proposal_id", "proposal_id"),)

    proposal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("remediation_proposals.id", ondelete="CASCADE"),
        nullable=False,
    )
    decision: Mapped[ApprovalDecision] = mapped_column(
        Enum(
            ApprovalDecision,
            name="remediation_approval_decision",
            values_callable=lambda e: [x.value for x in e],
            native_enum=False,
            length=16,
        ),
        nullable=False,
    )
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    proposal: Mapped[RemediationProposal] = relationship(back_populates="approvals")


class RemediationExecution(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "remediation_executions"
    __table_args__ = (Index("ix_remediation_executions_proposal_id", "proposal_id"),)

    proposal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("remediation_proposals.id", ondelete="CASCADE"),
        nullable=False,
    )
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    proposal: Mapped[RemediationProposal] = relationship(back_populates="executions")


class RemediationAuditLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "remediation_audit_logs"
    __table_args__ = (
        Index("ix_remediation_audit_logs_proposal_id", "proposal_id"),
        Index("ix_remediation_audit_logs_incident_id", "incident_id"),
    )

    proposal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    incident_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False, default="system")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
