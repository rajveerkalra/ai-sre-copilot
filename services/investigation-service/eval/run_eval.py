"""Evaluation harness for the deterministic RCA pipeline.

Runs every case in `golden_cases.GOLDEN_CASES` through the real
`build_evidence_catalog -> rule_based_rca -> validate_citations` pipeline
(the same functions the investigation-service graph calls when the LLM is
unavailable or in the LLM's own citation-guard path) and checks:

  1. root_cause_match   -- root cause text contains an expected keyword
  2. confidence_ok      -- confidence meets the case's minimum
  3. method_match        -- the expected rule fired (not a different one)
  4. citations_grounded -- every cited evidence_id is real (validate_citations
                           removed nothing) -- a regression guard against the
                           rule engine inventing evidence references
  5. required_ids_cited -- the evidence the case says must ground the RCA is
                           actually present in evidence_ids

This is intentionally scoped to the deterministic fallback path: it has no
external dependencies (no Ollama/model-gateway needed), runs in CI, and
catches regressions in the rule table itself. It does not evaluate the LLM
synthesis path, which is non-deterministic by nature -- see docs/eval.md
for why that's a separate, opt-in concern.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.evidence import build_evidence_catalog  # noqa: E402
from app.services.fallback import rule_based_rca, validate_citations  # noqa: E402
from eval.golden_cases import GOLDEN_CASES  # noqa: E402


def evaluate() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case in GOLDEN_CASES:
        evidence = build_evidence_catalog(case["context"])
        valid_ids = {e["evidence_id"] for e in evidence}
        rca = rule_based_rca(evidence=evidence, agent_outputs={}, runbooks=[])
        rca, removed = validate_citations(rca, valid_ids)

        root_cause_lower = rca["root_cause"].lower()
        checks = {
            "root_cause_match": any(
                kw.lower() in root_cause_lower for kw in case["expected_root_cause_keywords"]
            ),
            "confidence_ok": rca["confidence"] >= case["min_confidence"],
            "method_match": rca.get("method") == case["expected_method"],
            "citations_grounded": removed == [],
            "required_ids_cited": all(
                eid in rca["evidence_ids"] for eid in case["required_evidence_ids"]
            ),
        }
        passed = all(checks.values())
        results.append(
            {
                "name": case["name"],
                "category": case["category"],
                "passed": passed,
                "checks": checks,
                "actual": {
                    "root_cause": rca["root_cause"],
                    "confidence": rca["confidence"],
                    "method": rca.get("method"),
                    "evidence_ids": rca["evidence_ids"],
                    "removed_citations": removed,
                },
                "expected": {
                    "root_cause_keywords": case["expected_root_cause_keywords"],
                    "min_confidence": case["min_confidence"],
                    "method": case["expected_method"],
                    "required_evidence_ids": case["required_evidence_ids"],
                },
            }
        )

    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    return {
        "total": total,
        "passed": passed_count,
        "failed": total - passed_count,
        "pass_rate": (passed_count / total) if total else 0.0,
        "cases": results,
    }


def _print_report(report: dict[str, Any]) -> None:
    for case in report["cases"]:
        status = "PASS" if case["passed"] else "FAIL"
        print(f"[{status}] {case['name']} ({case['category']})")
        if not case["passed"]:
            for check_name, ok in case["checks"].items():
                if not ok:
                    print(f"         failed check: {check_name}")
            print(f"         expected: {case['expected']}")
            print(f"         actual:   {case['actual']}")
    print()
    print(
        f"{report['passed']}/{report['total']} passed "
        f"({report['pass_rate'] * 100:.1f}%)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the RCA golden-dataset evaluation")
    parser.add_argument(
        "--threshold",
        type=float,
        default=1.0,
        help="Minimum pass rate required to exit 0 (default: 1.0 -- deterministic rules "
        "must pass every golden case)",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path to write the full JSON report",
    )
    args = parser.parse_args()

    report = evaluate()
    _print_report(report)

    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2))
        print(f"\nWrote report to {args.json_out}")

    if report["pass_rate"] < args.threshold:
        print(
            f"\nFAIL: pass rate {report['pass_rate'] * 100:.1f}% "
            f"below threshold {args.threshold * 100:.1f}%"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
