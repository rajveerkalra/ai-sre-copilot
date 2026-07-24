"""API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import InvestigationStatus


class InvestigateRequest(BaseModel):
    correlation_id: str | None = None


class InvestigateResponse(BaseModel):
    accepted: bool
    investigation_id: uuid.UUID
    incident_id: uuid.UUID
    status: InvestigationStatus
    confidence: float | None = None
    used_fallback: bool = False
    duration_ms: float | None = None
    root_cause: str | None = None


class InvestigationDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    status: InvestigationStatus
    correlation_id: str
    model_name: str | None = None
    prompt_version: str
    used_fallback: bool
    confidence: float | None = None
    duration_ms: float | None = None
    report: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
