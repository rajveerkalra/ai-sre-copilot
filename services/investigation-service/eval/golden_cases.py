"""Golden dataset for the deterministic RCA evaluation harness.

Each case supplies a synthetic collector `context` (same shape produced by
context-service: metrics/logs/kubernetes/deployment/system/metadata) plus the
expected RCA outcome. The harness in `run_eval.py` runs each context through
the real `build_evidence_catalog` -> `rule_based_rca` -> `validate_citations`
pipeline and checks the result against these expectations.

Cases are deliberately isolated so exactly one rule in
`app/services/fallback.py` fires per case (rules are checked in order and the
first match wins) -- this pins down regressions in rule ordering/matching,
not just the rule table's final output.
"""

from __future__ import annotations

from typing import Any, TypedDict


class GoldenCase(TypedDict):
    name: str
    category: str
    context: dict[str, Any]
    expected_root_cause_keywords: list[str]
    min_confidence: float
    expected_method: str
    required_evidence_ids: list[str]


def _base_metadata(alertname: str, severity: str = "critical") -> dict[str, Any]:
    return {
        "incident": {
            "alertname": alertname,
            "severity": severity,
            "service": "sample-app",
            "title": alertname,
        }
    }


GOLDEN_CASES: list[GoldenCase] = [
    {
        "name": "error_storm_basic",
        "category": "error_storm",
        "context": {
            "metrics": {
                "series": {
                    "error_rate": {"current": 0.42, "trend": "up"},
                    "latency_p95": {"current": 1.2, "trend": "up"},
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
            "metadata": _base_metadata("HighErrorRate"),
        },
        "expected_root_cause_keywords": ["error"],
        "min_confidence": 85.0,
        "expected_method": "rule:error_storm",
        "required_evidence_ids": ["metric-error_rate", "log-summary", "incident-meta"],
    },
    {
        "name": "oom_kill",
        "category": "oomkilled",
        "context": {
            "metrics": {"series": {"cpu_usage": {"current": 0.2, "trend": "flat"}}},
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
            "kubernetes": {"available": False, "reason": "no kubeconfig", "issues": []},
            "deployment": {},
            "system": {"summary": {"host": "local"}},
            "metadata": _base_metadata("PodOOM"),
        },
        "expected_root_cause_keywords": ["memory", "oom"],
        "min_confidence": 88.0,
        "expected_method": "rule:oomkilled",
        "required_evidence_ids": ["log-summary"],
    },
    {
        "name": "crashloop_backoff",
        "category": "crashloop",
        "context": {
            "metrics": {"series": {}},
            "logs": {
                "summary": {
                    "error_count": 0,
                    "warning_count": 0,
                    "timeout_count": 0,
                    "oomkilled_count": 0,
                },
                "top_error_messages": [],
                "categories": {},
            },
            "kubernetes": {
                "available": True,
                "reason": None,
                "issues": [{"type": "CrashLoopBackOff", "reason": "restart limit exceeded"}],
            },
            "deployment": {},
            "system": {"summary": {"host": "local"}},
            "metadata": _base_metadata("PodCrashLoop"),
        },
        # "crashloopbackoff" is what the rule-based fallback literally outputs; the
        # LLM path was observed to correctly diagnose the same failure in different
        # words ("restart limit exceeded due to repeated pod crashes"), which is a
        # correct paraphrase, not a wrong answer -- these synonyms give the LLM eval
        # credit for that without loosening the rule-based eval (whose exact text
        # still only ever contains "crashloopbackoff").
        "expected_root_cause_keywords": [
            "crashloopbackoff",
            "crash loop",
            "restart limit",
            "repeated pod crash",
            "repeated crash",
        ],
        "min_confidence": 90.0,
        "expected_method": "rule:crashloop",
        "required_evidence_ids": ["k8s-issue-1"],
    },
    {
        "name": "latency_regression",
        "category": "latency",
        "context": {
            "metrics": {"series": {"latency_p95": {"current": 2.4, "trend": "up"}}},
            "logs": {
                "summary": {
                    "error_count": 0,
                    "warning_count": 0,
                    "timeout_count": 0,
                    "oomkilled_count": 0,
                },
                "top_error_messages": [],
                "categories": {},
            },
            "kubernetes": {"available": False, "reason": "no kubeconfig", "issues": []},
            "deployment": {},
            "system": {"summary": {"host": "local"}},
            "metadata": _base_metadata("HighLatency"),
        },
        "expected_root_cause_keywords": ["latency"],
        "min_confidence": 80.0,
        "expected_method": "rule:latency",
        "required_evidence_ids": ["metric-latency_p95"],
    },
    {
        "name": "cpu_saturation",
        "category": "cpu",
        "context": {
            "metrics": {"series": {"cpu_usage": {"current": 0.97, "trend": "up"}}},
            "logs": {
                "summary": {
                    "error_count": 0,
                    "warning_count": 0,
                    "timeout_count": 0,
                    "oomkilled_count": 0,
                },
                "top_error_messages": [],
                "categories": {},
            },
            "kubernetes": {"available": False, "reason": "no kubeconfig", "issues": []},
            "deployment": {},
            "system": {"summary": {"host": "local"}},
            "metadata": _base_metadata("HighCPU"),
        },
        "expected_root_cause_keywords": ["cpu"],
        "min_confidence": 82.0,
        "expected_method": "rule:cpu",
        "required_evidence_ids": ["metric-cpu_usage"],
    },
    {
        "name": "memory_pressure",
        "category": "memory",
        "context": {
            "metrics": {"series": {"memory_usage_bytes": {"current": 3.8e9, "trend": "up"}}},
            "logs": {
                "summary": {
                    "error_count": 0,
                    "warning_count": 0,
                    "timeout_count": 0,
                    "oomkilled_count": 0,
                },
                "top_error_messages": [],
                "categories": {},
            },
            "kubernetes": {"available": False, "reason": "no kubeconfig", "issues": []},
            "deployment": {},
            "system": {"summary": {"host": "local"}},
            "metadata": _base_metadata("HighMemory"),
        },
        "expected_root_cause_keywords": ["memory"],
        "min_confidence": 80.0,
        "expected_method": "rule:memory",
        "required_evidence_ids": ["metric-memory_usage_bytes"],
    },
    {
        "name": "dependency_timeout_cascade",
        "category": "dependency_timeout",
        "context": {
            "metrics": {"series": {"queue_depth": {"current": 400, "trend": "up"}}},
            "logs": {
                "summary": {
                    "error_count": 2,
                    "warning_count": 1,
                    "timeout_count": 5,
                    "oomkilled_count": 0,
                },
                "top_error_messages": [],
                "categories": {},
            },
            "kubernetes": {"available": False, "reason": "no kubeconfig", "issues": []},
            "deployment": {},
            "system": {"summary": {"host": "local"}},
            "metadata": _base_metadata("DependencyTimeout"),
        },
        "expected_root_cause_keywords": ["timeout"],
        "min_confidence": 84.0,
        "expected_method": "rule:dependency_timeout",
        "required_evidence_ids": ["log-summary"],
    },
    {
        "name": "deployment_regression",
        "category": "deployment_regression",
        "context": {
            "metrics": {"series": {}},
            "logs": {
                "summary": {},
                "top_error_messages": [
                    {"message": "errors climbing after rollout of app:v2", "count": 40},
                ],
                "categories": {},
            },
            "kubernetes": {"available": False, "reason": "no kubeconfig", "issues": []},
            "deployment": {
                "deployment_before_incident": {"image": "app:v2", "deployed_at": "T-5m"},
            },
            "system": {"summary": {"host": "local"}},
            "metadata": _base_metadata("DeploymentRegression"),
        },
        "expected_root_cause_keywords": ["deployment", "regression"],
        "min_confidence": 86.0,
        "expected_method": "rule:deployment_regression",
        "required_evidence_ids": ["deploy-before-incident"],
    },
    {
        "name": "insufficient_evidence_no_signal",
        "category": "insufficient_evidence",
        "context": {
            "metrics": {"series": {}},
            "logs": {"summary": {}, "top_error_messages": [], "categories": {}},
            "kubernetes": {"available": False, "reason": "no kubeconfig", "issues": []},
            "deployment": {},
            "system": {"summary": {"host": "local"}},
            "metadata": _base_metadata("NodeHealthCheck", severity="info"),
        },
        "expected_root_cause_keywords": ["insufficient evidence"],
        "min_confidence": 0.0,
        "expected_method": "rule:insufficient_evidence",
        "required_evidence_ids": [],
    },
    # --- Off-vocabulary adversarial cases -----------------------------------
    # Unlike the "no signal" case above, these have real, substantial evidence
    # -- just for an incident type none of the 8 rules were written for. This
    # is the robustness question docs/eval.md flags as untested: does the
    # rule engine correctly say "Insufficient evidence" for an unfamiliar
    # incident, or does it false-positive-match an unrelated rule because its
    # keyword matching is broader than intended? None of this evidence text
    # contains any of fallback.py's match keywords (cpu, latency, memory,
    # oomkilled, timeout, dependency, crashloop*, error_rate/error_storm,
    # deployment_regression's "deploy-before-incident" id) -- confirmed by
    # inspection of app/services/fallback.py's `match` lambdas.
    {
        "name": "dns_resolution_failure_offvocab",
        "category": "insufficient_evidence",
        "context": {
            "metrics": {"series": {"dns_lookup_failures": {"current": 42, "trend": "up"}}},
            "logs": {
                "summary": {
                    "error_count": 18,
                    "warning_count": 0,
                    "timeout_count": 0,
                    "oomkilled_count": 0,
                },
                "top_error_messages": [
                    {"message": "getaddrinfo ENOTFOUND upstream-service.internal", "count": 18},
                ],
                "categories": {},
            },
            "kubernetes": {"available": False, "reason": "no kubeconfig", "issues": []},
            "deployment": {},
            "system": {"summary": {"host": "local"}},
            "metadata": _base_metadata("DNSResolutionFailure"),
        },
        "expected_root_cause_keywords": ["insufficient evidence"],
        "min_confidence": 0.0,
        "expected_method": "rule:insufficient_evidence",
        "required_evidence_ids": [],
    },
    {
        "name": "tls_certificate_expiry_offvocab",
        "category": "insufficient_evidence",
        "context": {
            "metrics": {"series": {"cert_days_until_expiry": {"current": 2, "trend": "down"}}},
            "logs": {
                "summary": {
                    "error_count": 6,
                    "warning_count": 0,
                    "timeout_count": 0,
                    "oomkilled_count": 0,
                },
                "top_error_messages": [
                    {"message": "x509: certificate has expired or is not yet valid", "count": 6},
                ],
                "categories": {},
            },
            "kubernetes": {"available": False, "reason": "no kubeconfig", "issues": []},
            "deployment": {},
            "system": {"summary": {"host": "local"}},
            "metadata": _base_metadata("TLSCertificateExpiringSoon", severity="warning"),
        },
        "expected_root_cause_keywords": ["insufficient evidence"],
        "min_confidence": 0.0,
        "expected_method": "rule:insufficient_evidence",
        "required_evidence_ids": [],
    },
]
