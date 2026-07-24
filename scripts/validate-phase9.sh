#!/usr/bin/env bash
# Validate Phase 9 — portfolio & demo artifacts
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

pass=0
fail=0
ok() { echo "  OK  $1"; pass=$((pass + 1)); }
bad() { echo "  FAIL $1"; fail=$((fail + 1)); }

echo "==> Portfolio / demo files"
for f in \
  docs/architecture.md \
  docs/sequences.md \
  docs/API.md \
  docs/DEMO_SCRIPT.md \
  docs/SCREENSHOTS.md \
  docs/PHASE9.md \
  docs/PHASE9_VALIDATION.md \
  docs/demo/RECORDING.md \
  docs/portfolio/RESUME_BULLETS.md \
  docs/portfolio/LINKEDIN_POST.md \
  docs/portfolio/INTERVIEW_TALKING_POINTS.md \
  scripts/demo.sh
do
  if [[ -f "$f" ]]; then ok "$f"; else bad "missing $f"; fi
done

echo
echo "==> Diagram content"
if grep -q '```mermaid' docs/architecture.md && grep -q '```mermaid' docs/sequences.md; then
  ok "Mermaid diagrams present"
else
  bad "Mermaid fences missing"
fi

if grep -q 'flowchart' docs/architecture.md && grep -q 'sequenceDiagram' docs/sequences.md; then
  ok "architecture + sequence types"
else
  bad "expected flowchart/sequenceDiagram"
fi

echo
echo "==> README portfolio signals"
if grep -q 'Phase 9 complete' README.md && grep -q 'docs/architecture.md' README.md; then
  ok "README links Phase 9 + architecture"
else
  bad "README missing Phase 9/architecture links"
fi

if grep -q 'RESUME_BULLETS' README.md && grep -q 'DEMO_SCRIPT' README.md; then
  ok "README links portfolio + demo script"
else
  bad "README missing portfolio links"
fi

echo
echo "==> demo.sh executable + dry syntax"
if [[ -x scripts/demo.sh ]]; then ok "demo.sh executable"; else bad "chmod +x scripts/demo.sh"; fi
if bash -n scripts/demo.sh; then ok "demo.sh bash -n"; else bad "demo.sh syntax"; fi

echo
echo "Passed: $pass  Failed: $fail"
[[ "$fail" -eq 0 ]]
