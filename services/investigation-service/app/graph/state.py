"""Shared investigation state for LangGraph."""

from __future__ import annotations

from typing import Any, TypedDict


class InvestigationState(TypedDict, total=False):
    incident_id: str
    investigation_id: str
    correlation_id: str
    context: dict[str, Any]
    evidence: list[dict[str, Any]]
    metrics_result: dict[str, Any]
    logs_result: dict[str, Any]
    kubernetes_result: dict[str, Any]
    runbook_result: dict[str, Any]
    aggregated_evidence: list[dict[str, Any]]
    rca: dict[str, Any]
    report: dict[str, Any]
    used_fallback: bool
    model_name: str
    errors: list[str]
