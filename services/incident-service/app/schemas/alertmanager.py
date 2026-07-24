"""Alertmanager webhook payload schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AlertmanagerAlert(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = "firing"
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: datetime | None = None
    endsAt: datetime | None = None
    generatorURL: str | None = None
    fingerprint: str | None = None


class AlertmanagerWebhook(BaseModel):
    """Standard Alertmanager webhook notification body."""

    model_config = ConfigDict(extra="allow")

    version: str | None = None
    groupKey: str | None = None
    truncatedAlerts: int | None = None
    status: str = "firing"
    receiver: str | None = None
    groupLabels: dict[str, str] = Field(default_factory=dict)
    commonLabels: dict[str, str] = Field(default_factory=dict)
    commonAnnotations: dict[str, str] = Field(default_factory=dict)
    externalURL: str | None = None
    alerts: list[AlertmanagerAlert] = Field(default_factory=list)


class ParsedAlert(BaseModel):
    """Normalized alert fields used by the incident engine."""

    alertname: str
    severity: str
    namespace: str = ""
    pod: str = ""
    service: str = ""
    instance: str = ""
    status: str = "firing"
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    title: str = ""
    description: str = ""
    am_fingerprint: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
