"""Prometheus metrics."""

from __future__ import annotations

from prometheus_client import Counter, Histogram, Info

SERVICE_INFO = Info("remediation_service", "Remediation service metadata")

REMEDIATION_PROPOSALS_TOTAL = Counter(
    "remediation_proposals_total",
    "Proposals created",
    ["action_type"],
)
REMEDIATION_APPROVALS_TOTAL = Counter(
    "remediation_approvals_total",
    "Approval decisions",
    ["decision"],
)
REMEDIATION_EXECUTIONS_TOTAL = Counter(
    "remediation_executions_total",
    "Executions",
    ["status", "dry_run", "action_type"],
)
REMEDIATION_DURATION_SECONDS = Histogram(
    "remediation_duration_seconds",
    "Execution duration",
    ["action_type", "dry_run"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 15, 30),
)


def init_metrics(version: str, environment: str) -> None:
    SERVICE_INFO.info({"version": version, "environment": environment})
