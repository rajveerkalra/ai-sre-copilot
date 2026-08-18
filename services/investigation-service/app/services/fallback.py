"""Deterministic rule-based RCA when Ollama is unavailable."""

from __future__ import annotations

from typing import Any


def rule_based_rca(
    *,
    evidence: list[dict[str, Any]],
    agent_outputs: dict[str, Any],
    runbooks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Produce an evidence-cited RCA without LLM."""
    ids = {e["evidence_id"] for e in evidence}
    text_blob = " ".join(e.get("summary", "") for e in evidence).lower()
    alert = ""
    oomkilled_count = 0
    timeout_count = 0
    for e in evidence:
        if e["evidence_id"] == "incident-meta":
            alert = str((e.get("raw") or {}).get("alertname") or "").lower()
        if e["evidence_id"] == "log-summary":
            raw = e.get("raw") or {}
            try:
                oomkilled_count = int(raw.get("oomkilled_count") or 0)
            except (TypeError, ValueError):
                oomkilled_count = 0
            try:
                timeout_count = int(raw.get("timeout_count") or 0)
            except (TypeError, ValueError):
                timeout_count = 0

    rules = [
        {
            "name": "oomkilled",
            "match": lambda: oomkilled_count > 0
            or "oomkilled:" in text_blob
            or "out of memory" in text_blob,
            "root_cause": "Memory exhaustion leading to OOMKilled termination",
            "required": ["log-summary"],
            "impact": "Service restarts and request failures during OOM events",
            "steps": [
                "Increase memory limits",
                "Inspect for memory leaks",
                "Consider rollback if post-deploy",
            ],
            "confidence": 88.0,
        },
        {
            "name": "crashloop",
            "match": lambda: "crashloopbackoff" in text_blob,
            "root_cause": "Application startup failure causing CrashLoopBackOff",
            "required": [],
            "impact": "Pod unavailable; traffic may be degraded",
            "steps": [
                "Restart the affected container once config/secrets are fixed",
                "Inspect previous container logs",
                "Validate config/secrets",
                "Roll back bad image if correlated",
            ],
            "confidence": 90.0,
        },
        {
            "name": "error_storm",
            "match": lambda: "error_rate" in text_blob
            or "higherrorrate" in alert
            or "error_storm" in text_blob
            or "5xx" in text_blob,
            "root_cause": "Elevated application error rate (error storm)",
            "required": ["metric-error_rate", "log-summary", "incident-meta"],
            "impact": "User-facing failures and SLO burn",
            "steps": [
                "Correlate with recent deployment",
                "Inspect top error logs",
                "Disable fault injection if demo",
                "Roll back if regression confirmed",
            ],
            "confidence": 85.0,
        },
        {
            "name": "latency",
            "match": lambda: "latency" in text_blob or "highlatency" in alert,
            "root_cause": "Elevated request latency",
            "required": ["metric-latency_p95"],
            "impact": "Degraded user experience and timeout risk",
            "steps": [
                "Check dependency latency",
                "Inspect slow log paths",
                "Review recent deploy for performance regression",
            ],
            "confidence": 80.0,
        },
        {
            "name": "cpu",
            "match": lambda: "cpu" in text_blob or "highcpu" in alert or "cpu_burn" in text_blob,
            "root_cause": "CPU saturation",
            "required": ["metric-cpu_usage"],
            "impact": "Latency increase and potential request queuing",
            "steps": ["Scale horizontally", "Profile hot paths", "Clear CPU fault if injected"],
            "confidence": 82.0,
        },
        {
            "name": "memory",
            "match": lambda: "memory" in text_blob or "highmemory" in alert,
            "root_cause": "Elevated memory usage",
            "required": ["metric-memory_usage_bytes"],
            "impact": "Risk of OOM and restarts",
            "steps": ["Check ballast/leak", "Raise limits carefully", "Rollback if needed"],
            "confidence": 80.0,
        },
        {
            "name": "dependency_timeout",
            # NOT `"timeout" in text_blob`: log-summary's auto-generated
            # summary text always contains the literal substring "timeouts="
            # (see build_evidence_catalog in evidence.py) regardless of the
            # actual count, so that check matched almost any incident that
            # had a log-summary evidence item at all -- caught by an
            # adversarial golden case (DNS resolution failure, TLS cert
            # expiry) that has nothing to do with dependency timeouts.
            "match": lambda: timeout_count > 0 or "dependency" in text_blob,
            "root_cause": "Downstream dependency timeouts",
            "required": ["log-summary"],
            "impact": "504/timeout errors cascading to clients",
            "steps": [
                "Check dependency health",
                "Verify network policies",
                "Increase timeouts only as temporary mitigation",
            ],
            "confidence": 84.0,
        },
        {
            "name": "deployment_regression",
            "match": lambda: "deploy-before-incident" in ids
            and ("error" in text_blob or "latency" in text_blob),
            "root_cause": "Deployment regression — change preceded incident symptoms",
            "required": ["deploy-before-incident"],
            "impact": "Regression of availability/latency after rollout",
            "steps": ["Roll back deployment", "Compare image tags", "Add canary checks"],
            "confidence": 86.0,
        },
    ]

    for rule in rules:
        if not rule["match"]():
            continue
        cited = [eid for eid in rule["required"] if eid in ids]
        # Also cite matching evidence summaries
        for e in evidence:
            summary = e["summary"].lower()
            if rule["name"].split("_")[0] in summary or any(
                k in summary for k in rule["name"].split("_")
            ):
                if e["evidence_id"] not in cited:
                    cited.append(e["evidence_id"])
        if "incident-meta" in ids and "incident-meta" not in cited:
            cited.append("incident-meta")
        runbook_ids = [r.get("evidence_id") or f"runbook-{r.get('id', '')[:8]}" for r in runbooks[:3]]
        cited.extend([rid for rid in runbook_ids if rid])
        # Deduplicate preserve order
        seen = set()
        cited_unique = []
        for c in cited:
            if c and c not in seen:
                seen.add(c)
                cited_unique.append(c)
        if not cited_unique:
            continue
        return {
            "root_cause": rule["root_cause"],
            "confidence": rule["confidence"],
            "business_impact": rule["impact"],
            "next_steps": rule["steps"],
            "evidence_ids": cited_unique,
            "unknowns": [],
            "supporting_runbooks": runbooks[:3],
            "used_fallback": True,
            "method": f"rule:{rule['name']}",
        }

    # Insufficient evidence
    available = [e["evidence_id"] for e in evidence[:15]]
    return {
        "root_cause": "Insufficient evidence",
        "confidence": 0.0,
        "business_impact": "Unable to assess impact without stronger correlated signals",
        "next_steps": [
            "Re-run context collection",
            "Verify collectors succeeded",
            "Gather additional Kubernetes/deployment signals",
        ],
        "evidence_ids": available,
        "unknowns": ["Primary root cause undetermined from available evidence"],
        "supporting_runbooks": runbooks[:3],
        "used_fallback": True,
        "method": "rule:insufficient_evidence",
    }


def validate_citations(
    rca: dict[str, Any], valid_ids: set[str]
) -> tuple[dict[str, Any], list[str]]:
    """Drop invented evidence IDs; flag insufficient if none remain."""
    cited = list(rca.get("evidence_ids") or [])
    kept = [c for c in cited if c in valid_ids]
    removed = [c for c in cited if c not in valid_ids]
    rca = dict(rca)
    rca["evidence_ids"] = kept
    if removed:
        unknowns = list(rca.get("unknowns") or [])
        unknowns.append(f"Removed uncited/unknown evidence IDs: {removed}")
        rca["unknowns"] = unknowns
    if not kept and rca.get("root_cause") != "Insufficient evidence":
        rca["root_cause"] = "Insufficient evidence"
        rca["confidence"] = 0.0
        rca["unknowns"] = list(rca.get("unknowns") or []) + [
            "Citation validator rejected all evidence references"
        ]
    return rca, removed
