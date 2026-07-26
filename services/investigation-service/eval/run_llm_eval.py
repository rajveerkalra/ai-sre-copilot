"""Evaluation harness for the LLM RCA synthesis path (as opposed to the
deterministic rule fallback covered by run_eval.py).

This calls the *real* production code (`rca_synthesizer`, `citation_validator`
from app.agents.investigators) against a *live* model-gateway + Ollama, using
the same golden dataset as the rule-based eval. Unlike run_eval.py this is:

  - non-deterministic (LLM output varies run to run, temperature/model
    dependent)
  - slow (each case is a real network call to a real model; tens of seconds
    to minutes depending on hardware/model size)
  - environment-dependent (requires MODEL_GATEWAY_URL reachable and a model
    actually loaded -- it is NOT run in CI for this reason; see docs/eval.md)

It exists to answer, with an actual measured number instead of a guess,
"how accurate is the LLM RCA path" -- and to catch regressions where the
LLM path silently falls back (used_fallback=True) or gets its citations
stripped by the hallucination guard instead of producing a real answer.

Usage (from services/investigation-service, with model-gateway reachable):
    MODEL_GATEWAY_URL=http://localhost:8040 LLM_MODEL=llama3.2:1b \\
        PYTHONPATH=../..:. .venv/bin/python -m eval.run_llm_eval --json-out eval/llm-report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.investigators import citation_validator, rca_synthesizer  # noqa: E402
from app.services.evidence import build_evidence_catalog  # noqa: E402
from eval.golden_cases import GOLDEN_CASES  # noqa: E402


async def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    evidence = build_evidence_catalog(case["context"])
    state = {
        "incident_id": f"eval-{case['name']}",
        "investigation_id": f"eval-{case['name']}",
        "aggregated_evidence": evidence,
        "evidence": evidence,
        "metrics_result": {},
        "logs_result": {},
        "kubernetes_result": {},
        "runbook_result": {"runbooks": []},
    }

    started = time.perf_counter()
    synth_out = await rca_synthesizer(state)
    state.update(synth_out)
    validated = await citation_validator(state)
    rca = validated["rca"]
    elapsed_s = time.perf_counter() - started

    root_cause_lower = (rca.get("root_cause") or "").lower()
    root_cause_match = any(
        kw.lower() in root_cause_lower for kw in case["expected_root_cause_keywords"]
    )
    used_llm = not synth_out.get("used_fallback", True)

    return {
        "name": case["name"],
        "category": case["category"],
        "used_llm": used_llm,
        "root_cause_match": root_cause_match,
        "passed": used_llm and root_cause_match,
        "elapsed_s": round(elapsed_s, 1),
        "actual": {
            "root_cause": rca.get("root_cause"),
            "confidence": rca.get("confidence"),
            "evidence_ids": rca.get("evidence_ids"),
            "used_fallback": synth_out.get("used_fallback"),
        },
        "expected_root_cause_keywords": case["expected_root_cause_keywords"],
    }


async def evaluate() -> dict[str, Any]:
    results = []
    for case in GOLDEN_CASES:
        if case["category"] == "insufficient_evidence":
            # No positive root cause to match against; the rule-based eval
            # already covers this case. Skip it here to keep the LLM
            # accuracy number meaningful (it measures "did it find the
            # right cause", not "did it correctly say nothing was found").
            continue
        result = await _run_case(case)
        results.append(result)

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    used_llm_count = sum(1 for r in results if r["used_llm"])
    return {
        "total": total,
        "passed": passed,
        "used_llm_count": used_llm_count,
        "fallback_rate": 1 - (used_llm_count / total) if total else 0.0,
        "accuracy_when_llm_used": (
            sum(1 for r in results if r["used_llm"] and r["root_cause_match"]) / used_llm_count
            if used_llm_count
            else None
        ),
        "overall_pass_rate": (passed / total) if total else 0.0,
        "cases": results,
    }


def _print_report(report: dict[str, Any]) -> None:
    for case in report["cases"]:
        status = "PASS" if case["passed"] else "FAIL"
        llm_flag = "llm" if case["used_llm"] else "FALLBACK"
        print(
            f"[{status}] {case['name']} ({case['category']}) "
            f"[{llm_flag}, {case['elapsed_s']}s] -> {case['actual']['root_cause']!r}"
        )
    print()
    print(f"Cases: {report['total']}")
    print(f"Used real LLM (not fallback): {report['used_llm_count']}/{report['total']}")
    print(f"Fallback rate: {report['fallback_rate'] * 100:.1f}%")
    if report["accuracy_when_llm_used"] is not None:
        print(
            f"Root-cause accuracy when LLM actually ran: "
            f"{report['accuracy_when_llm_used'] * 100:.1f}%"
        )
    print(f"Overall pass rate (used LLM AND correct): {report['overall_pass_rate'] * 100:.1f}%")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the LLM RCA synthesis evaluation")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    report = asyncio.run(evaluate())
    _print_report(report)

    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2))
        print(f"\nWrote report to {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
