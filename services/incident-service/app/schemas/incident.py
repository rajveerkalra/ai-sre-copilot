"""Incident API request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import IncidentSeverity, IncidentStatus, TimelineEventType


class TimelineEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: TimelineEventType
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @field_validator("metadata", mode="before")
    @classmethod
    def coerce_metadata(cls, value: Any) -> Any:
        # ORM attribute is metadata_
        if value is None:
            return {}
        return value


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: IncidentStatus
    severity: IncidentSeverity
    fingerprint: str
    occurrence_count: int
    alertname: str | None = None
    service: str | None = None
    namespace: str | None = None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None


class IncidentListResponse(BaseModel):
    items: list[IncidentResponse]
    total: int
    page: int
    page_size: int
    pages: int


class IncidentDetailResponse(IncidentResponse):
    timeline: list[TimelineEventResponse] = Field(default_factory=list)


class NoteCreateRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class TimelineEventCreateRequest(BaseModel):
    event_type: TimelineEventType
    message: str = Field(..., min_length=1, max_length=4000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResolveRequest(BaseModel):
    message: str | None = Field(
        default=None,
        max_length=4000,
        description="Optional resolution note",
    )


class WebhookProcessResult(BaseModel):
    incident_id: uuid.UUID
    fingerprint: str
    action: str  # created | deduplicated | resolved
    occurrence_count: int
    alertname: str
    title: str = ""
    severity: str = ""
    service: str = ""


class WebhookIngestResponse(BaseModel):
    accepted: bool
    alert_count: int
    results: list[WebhookProcessResult]
