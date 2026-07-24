#!/usr/bin/env bash
# Validate Phase 6 — executive dashboard + proxied APIs
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/auth.sh
source "$ROOT/scripts/lib/auth.sh"

pass=0
fail=0

AH="$(auth_header operator operator123)"

check() {
  local name="$1"
  local url="$2"
  local expect="${3:-200}"
  local use_auth="${4:-0}"
  if [[ "$use_auth" == "1" ]]; then
    code="$(curl -s -o /dev/null -w '%{http_code}' -H "$AH" "$url" || echo 000)"
  else
    code="$(curl -s -o /dev/null -w '%{http_code}' "$url" || echo 000)"
  fi
  if [[ "$code" == "$expect" ]]; then
    echo "  OK  $name ($code)"
    pass=$((pass + 1))
  else
    echo "  FAIL $name (got $code, want $expect) — $url"
    fail=$((fail + 1))
  fi
}

echo "==> Phase 6 health"
check "dashboard health" "http://localhost:8050/health"
check "dashboard ready" "http://localhost:8050/ready"
check "dashboard index" "http://localhost:8050/"

echo
echo "==> Proxied backend APIs"
check "proxy incidents" "http://localhost:8050/proxy/incident/incidents?page_size=1" 200 1
check "proxy pending remediations" "http://localhost:8050/proxy/remediation/remediations/pending" 200 1
check "proxy investigation health" "http://localhost:8050/proxy/investigation/health"
check "proxy context health" "http://localhost:8050/proxy/context/health"
check "proxy auth health" "http://localhost:8050/proxy/auth/health"

echo
echo "==> UI asset"
html="$(curl -sf http://localhost:8050/ || true)"
if echo "$html" | grep -q 'SRE Copilot'; then
  echo "  OK  index title present"
  pass=$((pass + 1))
else
  echo "  FAIL index missing title"
  fail=$((fail + 1))
fi

echo
echo "Passed: $pass  Failed: $fail"
[[ "$fail" -eq 0 ]]
