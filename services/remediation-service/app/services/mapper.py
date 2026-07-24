"""Deterministic RCA → remediation proposal mapping (no LLM)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.models import ActionType, RiskLevel


def map_rca_to_proposals(
    *,
    incident_id: UUID,
    investigation_id: UUID | None,
    rca: dict[str, Any],
) -> list[dict[str, Any]]:
    """Produce structured remediation proposals from an RCA payload."""
    root = str(rca.get("root_cause") or "").lower()
    steps = [str(s).lower() for s in (rca.get("next_steps") or [])]
    blob = " ".join([root, *steps])
    evidence_ids = list(rca.get("evidence_ids") or [])
    confidence = float(rca.get("confidence") or 0)
    root_cause = str(rca.get("root_cause") or "Insufficient evidence")

    proposals: list[dict[str, Any]] = []

    def add(
        *,
        action_type: ActionType,
        title: str,
        rationale: str,
        parameters: dict[str, Any],
        risk: RiskLevel,
        dry_default: bool,
        conf: float | None = None,
    ) -> None:
        proposals.append(
            {
                "incident_id": incident_id,
                "investigation_id": investigation_id,
                "action_type": action_type,
                "title": title,
                "rationale": rationale,
                "parameters": parameters,
                "confidence": conf if conf is not None else confidence,
                "risk_level": risk,
                "requires_dry_run_default": dry_default,
                "evidence_ids": evidence_ids,
                "root_cause": root_cause,
            }
        )

    # Fault-clear (safe demo path)
    if any(
        k in blob
        for k in (
            "error storm",
            "error rate",
            "elevated application error",
            "5xx",
        )
    ):
        add(
            action_type=ActionType.CLEAR_FAULT,
            title="Clear sample-app error_storm fault injection",
            rationale="RCA indicates elevated error rate consistent with demo fault injection.",
            parameters={"fault": "error_storm", "endpoint": "deactivate"},
            risk=RiskLevel.LOW,
            dry_default=False,
            conf=max(confidence, 80.0),
        )
    if ("cpu" in blob and "saturation" in blob) or "cpu saturation" in blob or "cpu_spike" in blob:
        add(
            action_type=ActionType.CLEAR_FAULT,
            title="Clear sample-app cpu_spike fault",
            rationale="RCA cites CPU saturation; clear injected CPU fault if present.",
            parameters={"fault": "cpu_spike", "endpoint": "deactivate"},
            risk=RiskLevel.LOW,
            dry_default=False,
        )
    if "memory" in blob or "oom" in blob:
        add(
            action_type=ActionType.CLEAR_FAULT,
            title="Clear sample-app memory_leak fault",
            rationale="Memory-related RCA; clear injected memory fault if present.",
            parameters={"fault": "memory_leak", "endpoint": "deactivate"},
            risk=RiskLevel.LOW,
            dry_default=False,
        )
    if "latency" in blob:
        add(
            action_type=ActionType.CLEAR_FAULT,
            title="Clear sample-app latency fault",
            rationale="Latency RCA; clear injected latency fault if present.",
            parameters={"fault": "latency", "endpoint": "deactivate"},
            risk=RiskLevel.LOW,
            dry_default=False,
        )
    if "timeout" in blob or "dependency" in blob:
        add(
            action_type=ActionType.CLEAR_FAULT,
            title="Clear sample-app dependency_timeout fault",
            rationale="Dependency timeout RCA; clear injected timeout fault if present.",
            parameters={"fault": "dependency_timeout", "endpoint": "deactivate"},
            risk=RiskLevel.LOW,
            dry_default=False,
        )

    # Risky / dry-run defaults
    if "roll back" in blob or "rollback" in blob or "regression" in blob:
        add(
            action_type=ActionType.ROLLBACK,
            title="Propose deployment rollback (dry-run)",
            rationale="RCA suggests deployment regression; rollback requires approval and remains dry-run locally.",
            parameters={"target": "sample-app", "strategy": "previous_revision"},
            risk=RiskLevel.HIGH,
            dry_default=True,
        )
    if "scale" in blob:
        add(
            action_type=ActionType.SCALE,
            title="Propose horizontal scale-out (dry-run)",
            rationale="RCA suggests scaling; local Compose scale is dry-run unless mutations enabled.",
            parameters={"service": "sample-app", "replicas": 2},
            risk=RiskLevel.MEDIUM,
            dry_default=True,
        )
    if "restart" in blob:
        add(
            action_type=ActionType.RESTART_SERVICE,
            title="Propose sample-app restart",
            rationale="RCA suggests restart; Compose restart gated by ALLOW_COMPOSE_RESTART.",
            parameters={"service": "sample-app"},
            risk=RiskLevel.MEDIUM,
            dry_default=True,
        )

    # Always offer a manual runbook follow-up when we have any RCA
    if root_cause and root_cause != "Insufficient evidence":
        add(
            action_type=ActionType.RUNBOOK_MANUAL,
            title="Follow supporting runbook steps manually",
            rationale="Human operators should validate automated proposals against runbooks.",
            parameters={"next_steps": rca.get("next_steps") or []},
            risk=RiskLevel.LOW,
            dry_default=True,
            conf=min(confidence, 60.0),
        )
    elif not proposals:
        add(
            action_type=ActionType.RUNBOOK_MANUAL,
            title="Insufficient evidence — gather more context",
            rationale="No automated remediation is safe without a cited root cause.",
            parameters={"next_steps": rca.get("next_steps") or []},
            risk=RiskLevel.LOW,
            dry_default=True,
            conf=0.0,
        )

    # Deduplicate by action_type + title
    seen: set[str] = set()
    unique = []
    for p in proposals:
        key = f"{p['action_type'].value}:{p['title']}"
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique
