"""Unit tests — evidence catalog, fallback RCA, citation validator."""

from __future__ import annotations

from app.services.evidence import build_evidence_catalog
from app.services.fallback import rule_based_rca, validate_citations


SAMPLE_CONTEXT = {
    "metrics": {
        "series": {
            "error_rate": {"current": 0.42, "trend": "up"},
            "latency_p95": {"current": 1.2, "trend": "up"},
            "cpu_usage": {"current": 0.3, "trend": "flat"},
        }
    },
    "logs": {
        "summary": {
            "error_count": 120,
            "warning_count": 10,
            "timeout_count": 0,
            "oomkilled_count": 0,
        },
        "top_error_messages": [
            {"message": "error_storm injected failure", "count": 95},
        ],
        "categories": {"error": 120},
    },
    "kubernetes": {"available": False, "reason": "no kubeconfig", "issues": []},
    "deployment": {},
    "system": {"summary": {"host": "local"}},
    "metadata": {
        "incident": {
            "alertname": "HighErrorRate",
            "severity": "critical",
            "service": "sample-app",
            "title": "High error rate",
        }
    },
}


def test_build_evidence_catalog_ids():
    items = build_evidence_catalog(SAMPLE_CONTEXT)
    ids = {e["evidence_id"] for e in items}
    assert "metric-error_rate" in ids
    assert "log-summary" in ids
    assert "incident-meta" in ids
    assert "k8s-unavailable" in ids


def test_rule_based_error_storm():
    evidence = build_evidence_catalog(SAMPLE_CONTEXT)
    rca = rule_based_rca(evidence=evidence, agent_outputs={}, runbooks=[])
    assert rca["root_cause"] != "Insufficient evidence"
    assert rca["confidence"] > 0
    assert rca["used_fallback"] is True
    assert "metric-error_rate" in rca["evidence_ids"]
    assert all(isinstance(e, str) for e in rca["evidence_ids"])


def test_rule_based_oom():
    ctx = {
        **SAMPLE_CONTEXT,
        "logs": {
            "summary": {
                "error_count": 5,
                "warning_count": 0,
                "timeout_count": 0,
                "oomkilled_count": 3,
            },
            "top_error_messages": [{"message": "OOMKilled", "count": 3}],
            "categories": {},
        },
        "metadata": {"incident": {"alertname": "PodOOM", "severity": "critical"}},
    }
    evidence = build_evidence_catalog(ctx)
    # Force OOM text into summaries
    evidence.append(
        {
            "evidence_id": "k8s-issue-1",
            "source": "kubernetes",
            "summary": "OOMKilled: pod sample-app",
            "raw": {"type": "OOMKilled"},
        }
    )
    rca = rule_based_rca(evidence=evidence, agent_outputs={}, runbooks=[])
    assert "Memory exhaustion" in rca["root_cause"] or "OOM" in rca["root_cause"]
    assert rca["confidence"] >= 80


def test_citation_validator_strips_unknown():
    rca = {
        "root_cause": "Something invented",
        "confidence": 99,
        "evidence_ids": ["metric-error_rate", "fake-id-999"],
        "unknowns": [],
    }
    fixed, removed = validate_citations(rca, {"metric-error_rate"})
    assert removed == ["fake-id-999"]
    assert fixed["evidence_ids"] == ["metric-error_rate"]
    assert fixed["root_cause"] == "Something invented"


def test_citation_validator_insufficient_when_empty():
    rca = {
        "root_cause": "Hallucinated cause",
        "confidence": 50,
        "evidence_ids": ["totally-fake"],
        "unknowns": [],
    }
    fixed, removed = validate_citations(rca, {"metric-error_rate"})
    assert fixed["root_cause"] == "Insufficient evidence"
    assert fixed["confidence"] == 0.0
    assert removed == ["totally-fake"]


def test_insufficient_when_no_match():
    evidence = [
        {
            "evidence_id": "misc-1",
            "source": "system",
            "summary": "benign noise",
            "raw": {},
        }
    ]
    rca = rule_based_rca(evidence=evidence, agent_outputs={}, runbooks=[])
    assert rca["root_cause"] == "Insufficient evidence"
    assert rca["confidence"] == 0.0
