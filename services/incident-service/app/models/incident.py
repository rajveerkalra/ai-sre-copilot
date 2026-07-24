"""ORM models for incidents, timeline, and alert payloads."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class IncidentStatus(str, enum.Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class IncidentSeverity(str, enum.Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    UNKNOWN = "unknown"


class TimelineEventType(str, enum.Enum):
    INCIDENT_CREATED = "incident_created"
    ALERT_RECEIVED = "alert_received"
    ALERT_REPEATED = "alert_repeated"
    INCIDENT_UPDATED = "incident_updated"
    INCIDENT_RESOLVED = "incident_resolved"
    NOTE_ADDED = "note_added"
    CONTEXT_COLLECTION_TRIGGERED = "context_collection_triggered"
    REMEDIATION_PROPOSED = "remediation_proposed"
    REMEDIATION_APPROVED = "remediation_approved"
    REMEDIATION_REJECTED = "remediation_rejected"
    REMEDIATION_EXECUTED = "remediation_executed"


# JSONB on Postgres; plain JSON for SQLite unit tests
JSONType = JSON().with_variant(JSONB(), "postgresql")


class Incident(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "incidents"
    __table_args__ = (
        Index(
            "ux_incidents_open_fingerprint",
            "fingerprint",
            unique=True,
            postgresql_where=text("status = 'open'"),
            sqlite_where=text("status = 'open'"),
        ),
        Index("ix_incidents_status_severity", "status", "severity"),
    )

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(
            IncidentStatus,
            name="incident_status",
            values_callable=lambda e: [x.value for x in e],
            native_enum=False,
            length=32,
        ),
        nullable=False,
        default=IncidentStatus.OPEN,
        index=True,
    )
    severity: Mapped[IncidentSeverity] = mapped_column(
        Enum(
            IncidentSeverity,
            name="incident_severity",
            values_callable=lambda e: [x.value for x in e],
            native_enum=False,
            length=32,
        ),
        nullable=False,
        default=IncidentSeverity.UNKNOWN,
        index=True,
    )
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    alertname: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    service: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    namespace: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    timeline_events: Mapped[list[TimelineEvent]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="TimelineEvent.created_at",
    )
    alert_payloads: Mapped[list[AlertPayload]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
    )


class TimelineEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "timeline_events"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[TimelineEventType] = mapped_column(
        Enum(
            TimelineEventType,
            name="timeline_event_type",
            values_callable=lambda e: [x.value for x in e],
            native_enum=False,
            length=64,
        ),
        nullable=False,
        index=True,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONType,
        nullable=False,
        default=dict,
    )

    incident: Mapped[Incident] = relationship(back_populates="timeline_events")


class AlertPayload(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "alert_payloads"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    incident: Mapped[Incident] = relationship(back_populates="alert_payloads")
