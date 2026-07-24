"""API schemas for context-service."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import CollectorRunStatus, ContextStatus


class CollectRequest(BaseModel):
    correlation_id: str | None = None
    force: bool = False


class CollectorRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    collector_name: str
    status: CollectorRunStatus
    attempt_count: int
    duration_ms: float | None = None
    started_at: datetime
    finished_at: datetime | None = None


class InvestigationContextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    status: ContextStatus
    correlation_id: str
    collected_at: datetime | None = None
    duration_ms: float | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    logs: dict[str, Any] = Field(default_factory=dict)
    kubernetes: dict[str, Any] = Field(default_factory=dict)
    deployment: dict[str, Any] = Field(default_factory=dict)
    system: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    collector_runs: list[CollectorRunResponse] = Field(default_factory=list)
    created_at: datetime


class CollectAcceptedResponse(BaseModel):
    accepted: bool
    incident_id: uuid.UUID
    context_id: uuid.UUID
    status: ContextStatus
    correlation_id: str
    duration_ms: float | None = None
