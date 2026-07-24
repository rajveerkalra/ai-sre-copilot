"""Evidence extraction — every finding gets a stable evidence_id."""

from __future__ import annotations

from typing import Any


def build_evidence_catalog(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten context collectors into citeable evidence items."""
    items: list[dict[str, Any]] = []
    metrics = context.get("metrics") or {}
    series = metrics.get("series") or {}
    for name, payload in series.items():
        current = (payload or {}).get("current")
        trend = (payload or {}).get("trend")
        eid = f"metric-{name}"
        items.append(
            {
                "evidence_id": eid,
                "source": "metrics",
                "summary": f"{name} current={current} trend={trend}",
                "raw": {"name": name, **(payload or {})},
            }
        )

    logs = context.get("logs") or {}
    for i, top in enumerate((logs.get("top_error_messages") or [])[:10]):
        eid = f"log-top-{i+1}"
        items.append(
            {
                "evidence_id": eid,
                "source": "logs",
                "summary": f"Top error ({top.get('count')}x): {str(top.get('message', ''))[:160]}",
                "raw": top,
            }
        )
    summary = logs.get("summary") or {}
    if summary:
        items.append(
            {
                "evidence_id": "log-summary",
                "source": "logs",
                "summary": (
                    f"errors={summary.get('error_count')} warnings={summary.get('warning_count')} "
                    f"timeouts={summary.get('timeout_count')} oomkilled={summary.get('oomkilled_count')}"
                ),
                "raw": summary,
            }
        )

    k8s = context.get("kubernetes") or {}
    for i, issue in enumerate((k8s.get("issues") or [])[:20]):
        eid = f"k8s-issue-{i+1}"
        items.append(
            {
                "evidence_id": eid,
                "source": "kubernetes",
                "summary": f"{issue.get('type')}: {issue}",
                "raw": issue,
            }
        )
    if k8s.get("available") is False:
        items.append(
            {
                "evidence_id": "k8s-unavailable",
                "source": "kubernetes",
                "summary": f"Kubernetes unavailable: {k8s.get('reason')}",
                "raw": {"reason": k8s.get("reason")},
            }
        )

    deployment = context.get("deployment") or {}
    dep_before = deployment.get("deployment_before_incident")
    if dep_before:
        items.append(
            {
                "evidence_id": "deploy-before-incident",
                "source": "deployment",
                "summary": f"Deployment change before incident: {dep_before}",
                "raw": dep_before,
            }
        )
    for i, img in enumerate((deployment.get("recent_images") or [])[:10]):
        items.append(
            {
                "evidence_id": f"deploy-image-{i+1}",
                "source": "deployment",
                "summary": f"Recent image: {img}",
                "raw": {"image": img},
            }
        )

    system = context.get("system") or {}
    sys_summary = system.get("summary") or {}
    if sys_summary:
        items.append(
            {
                "evidence_id": "system-summary",
                "source": "system",
                "summary": str(sys_summary),
                "raw": sys_summary,
            }
        )
    for i, c in enumerate((system.get("docker") or {}).get("containers") or []):
        if c.get("health") and c.get("health") != "healthy":
            items.append(
                {
                    "evidence_id": f"system-unhealthy-{i+1}",
                    "source": "system",
                    "summary": f"Unhealthy container {c.get('name')} health={c.get('health')}",
                    "raw": c,
                }
            )

    meta = (context.get("metadata") or {}).get("incident") or {}
    if meta:
        items.append(
            {
                "evidence_id": "incident-meta",
                "source": "incident",
                "summary": (
                    f"alert={meta.get('alertname')} severity={meta.get('severity')} "
                    f"service={meta.get('service')}"
                ),
                "raw": meta,
            }
        )
    return items


def evidence_index(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {e["evidence_id"]: e for e in items}
