"""Investigation ORM models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow

JSONType = JSON().with_variant(JSONB(), "postgresql")


class InvestigationStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class InvestigationRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "investigation_runs"
    __table_args__ = (Index("ix_investigation_runs_incident_id", "incident_id"),)

    incident_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[InvestigationStatus] = mapped_column(
        Enum(
            InvestigationStatus,
            name="investigation_status",
            values_callable=lambda e: [x.value for x in e],
            native_enum=False,
            length=32,
        ),
        nullable=False,
        default=InvestigationStatus.PENDING,
    )
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    used_fallback: Mapped[bool] = mapped_column(default=False, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    report: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONType, nullable=False, default=dict
    )

    evidence_items: Mapped[list[Evidence]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan"
    )
    agent_results: Mapped[list[AgentResult]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan"
    )
    rca_report: Mapped[Optional[RCAReport]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan", uselist=False
    )


class Evidence(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "evidence"
    __table_args__ = (Index("ix_evidence_investigation_id", "investigation_id"),)

    investigation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("investigation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    investigation: Mapped[InvestigationRun] = relationship(back_populates="evidence_items")


class AgentResult(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "agent_results"
    __table_args__ = (Index("ix_agent_results_investigation_id", "investigation_id"),)

    investigation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("investigation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    output: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    used_llm: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    investigation: Mapped[InvestigationRun] = relationship(back_populates="agent_results")


class RCAReport(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "rca_reports"

    investigation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("investigation_runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    business_impact: Mapped[str] = mapped_column(Text, nullable=False, default="")
    next_steps: Mapped[list[Any]] = mapped_column(JSONType, nullable=False, default=list)
    evidence_ids: Mapped[list[Any]] = mapped_column(JSONType, nullable=False, default=list)
    unknowns: Mapped[list[Any]] = mapped_column(JSONType, nullable=False, default=list)
    supporting_runbooks: Mapped[list[Any]] = mapped_column(
        JSONType, nullable=False, default=list
    )
    used_fallback: Mapped[bool] = mapped_column(default=False, nullable=False)
    full_report: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    investigation: Mapped[InvestigationRun] = relationship(back_populates="rca_report")
