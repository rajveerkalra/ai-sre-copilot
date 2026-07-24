"""Remediation executors — approval-gated; dry-run for risky actions."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from app.config import Settings, get_settings
from app.models import ActionType, RemediationProposal

logger = structlog.get_logger(__name__)


class ExecutionError(Exception):
    pass


def resolve_dry_run(proposal: RemediationProposal, *, requested_dry_run: bool | None) -> bool:
    settings = get_settings()
    if requested_dry_run is True:
        return True
    if proposal.requires_dry_run_default and not settings.allow_mutations:
        return True
    if proposal.action_type in {
        ActionType.ROLLBACK,
        ActionType.SCALE,
    } and not settings.allow_mutations:
        return True
    if (
        proposal.action_type == ActionType.RESTART_SERVICE
        and not settings.allow_compose_restart
    ):
        return True
    if requested_dry_run is False and proposal.requires_dry_run_default:
        # Explicit live request still blocked for high-risk without allow_mutations
        if proposal.risk_level.value == "high" and not settings.allow_mutations:
            return True
    return bool(requested_dry_run) if requested_dry_run is not None else False


async def execute_proposal(
    proposal: RemediationProposal,
    *,
    dry_run: bool,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    if not settings.execution_enabled:
        raise ExecutionError("Execution disabled (EXECUTION_ENABLED=false)")

    action = proposal.action_type
    params = proposal.parameters or {}

    if dry_run:
        return {
            "dry_run": True,
            "action_type": action.value,
            "would_execute": params,
            "message": f"Dry-run: would execute {action.value}",
        }

    if action == ActionType.CLEAR_FAULT:
        return await _clear_fault(params, settings)
    if action == ActionType.RUNBOOK_MANUAL:
        return {
            "dry_run": False,
            "action_type": action.value,
            "message": "Manual runbook acknowledged — no automated mutation",
            "next_steps": params.get("next_steps") or [],
        }
    if action == ActionType.RESTART_SERVICE:
        if not settings.allow_compose_restart:
            raise ExecutionError("Compose restart not allowed (ALLOW_COMPOSE_RESTART=false)")
        return {
            "dry_run": False,
            "action_type": action.value,
            "message": "Compose restart requested (local stub — operator must restart container)",
            "service": params.get("service"),
        }
    if action in {ActionType.ROLLBACK, ActionType.SCALE}:
        if not settings.allow_mutations:
            raise ExecutionError("Mutations not allowed for this action without ALLOW_MUTATIONS")
        return {
            "dry_run": False,
            "action_type": action.value,
            "message": "Mutation stub recorded (no cluster API wired in Phase 5)",
            "parameters": params,
        }
    raise ExecutionError(f"Unsupported action: {action}")


async def _clear_fault(params: dict[str, Any], settings: Settings) -> dict[str, Any]:
    base = settings.sample_app_url.rstrip("/")
    fault = params.get("fault") or "error_storm"
    endpoint = params.get("endpoint") or "deactivate"
    if fault == "all" or endpoint == "deactivate-all":
        url = f"{base}/faults/deactivate-all"
    else:
        url = f"{base}/faults/{fault}/deactivate"
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        resp = await client.post(url)
        if resp.status_code >= 400:
            raise ExecutionError(f"sample-app fault clear failed: {resp.status_code} {resp.text[:200]}")
        body = {}
        try:
            body = resp.json()
        except Exception:  # noqa: BLE001
            body = {"raw": resp.text[:200]}
    logger.info("fault_cleared", fault=fault, url=url)
    return {
        "dry_run": False,
        "action_type": ActionType.CLEAR_FAULT.value,
        "fault": fault,
        "sample_app_response": body,
        "message": f"Cleared fault {fault}",
    }
