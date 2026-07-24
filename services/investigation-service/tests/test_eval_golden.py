"""Runs the golden-dataset RCA evaluation as part of the normal test suite.

See eval/run_eval.py for the harness itself and eval/golden_cases.py for the
dataset. This keeps the eval gated in CI without needing a separate command.
"""

from __future__ import annotations

from eval.run_eval import evaluate


def test_golden_rca_eval_passes():
    report = evaluate()
    failures = [c for c in report["cases"] if not c["passed"]]
    assert not failures, (
        f"{len(failures)}/{report['total']} golden RCA cases failed: "
        f"{[(c['name'], c['checks']) for c in failures]}"
    )
