"""ORM models for investigation context storage."""

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


class ContextStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class CollectorRunStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class InvestigationContext(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "investigation_context"
    __table_args__ = (
        Index("ix_investigation_context_incident_id", "incident_id"),
        Index("ix_investigation_context_status", "status"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[ContextStatus] = mapped_column(
        Enum(
            ContextStatus,
            name="context_status",
            values_callable=lambda e: [x.value for x in e],
            native_enum=False,
            length=32,
        ),
        nullable=False,
        default=ContextStatus.PENDING,
    )
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    collected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Full normalized investigation context blob
    context: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    # Denormalized slices for fast section APIs
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    logs: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    kubernetes: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    deployment: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    system: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONType, nullable=False, default=dict
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    collector_runs: Mapped[list[CollectorRun]] = relationship(
        back_populates="investigation_context",
        cascade="all, delete-orphan",
        order_by="CollectorRun.started_at",
    )


class CollectorRun(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "collector_runs"
    __table_args__ = (
        Index("ix_collector_runs_context_id", "investigation_context_id"),
        Index("ix_collector_runs_collector_name", "collector_name"),
    )

    investigation_context_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("investigation_context.id", ondelete="CASCADE"),
        nullable=False,
    )
    collector_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[CollectorRunStatus] = mapped_column(
        Enum(
            CollectorRunStatus,
            name="collector_run_status",
            values_callable=lambda e: [x.value for x in e],
            native_enum=False,
            length=32,
        ),
        nullable=False,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    output: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    investigation_context: Mapped[InvestigationContext] = relationship(
        back_populates="collector_runs"
    )
    errors: Mapped[list[CollectorError]] = relationship(
        back_populates="collector_run",
        cascade="all, delete-orphan",
    )


class CollectorError(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "collector_errors"
    __table_args__ = (Index("ix_collector_errors_run_id", "collector_run_id"),)

    collector_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("collector_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    error_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    collector_run: Mapped[CollectorRun] = relationship(back_populates="errors")
