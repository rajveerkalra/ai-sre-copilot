"""API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import ActionType, ProposalStatus, RiskLevel


class ApproveRequest(BaseModel):
    approved_by: str = Field(..., min_length=1, max_length=128)
    comment: str = ""


class RejectRequest(BaseModel):
    rejected_by: str = Field(..., min_length=1, max_length=128)
    comment: str = ""


class ExecuteRequest(BaseModel):
    dry_run: bool | None = None
    actor: str = "operator"


class ProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    investigation_id: uuid.UUID | None = None
    action_type: ActionType
    title: str
    rationale: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: float
    risk_level: RiskLevel
    requires_dry_run_default: bool
    status: ProposalStatus
    evidence_ids: list[Any] = Field(default_factory=list)
    root_cause: str
    created_at: datetime
    updated_at: datetime


class ProposeResponse(BaseModel):
    incident_id: uuid.UUID
    count: int
    proposals: list[ProposalResponse]


class ExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    proposal_id: uuid.UUID
    dry_run: bool
    status: str
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: float | None = None
