#!/usr/bin/env bash
# Validate Phase 7 — auth, RBAC, OTel, API versioning, probes
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/auth.sh
source "$ROOT/scripts/lib/auth.sh"

pass=0
fail=0

check() {
  local name="$1"
  local url="$2"
  local expect="${3:-200}"
  local hdr="${4:-}"
  if [[ -n "$hdr" ]]; then
    code="$(curl -s -o /dev/null -w '%{http_code}' -H "$hdr" "$url" || echo 000)"
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

echo "==> Auth service"
check "auth health" "http://localhost:8060/health"
check "auth ready" "http://localhost:8060/ready"
check "auth metrics" "http://localhost:8060/metrics"

TOKEN="$(auth_login operator operator123 || true)"
if [[ -n "${TOKEN:-}" ]]; then
  echo "  OK  login issued token"
  pass=$((pass + 1))
else
  echo "  FAIL login"
  fail=$((fail + 1))
  TOKEN="invalid"
fi

AH="Authorization: Bearer ${TOKEN}"
check "auth me" "http://localhost:8060/auth/me" 200 "$AH"

code="$(curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8060/api/v1/auth/login \
  -H 'Content-Type: application/json' -d '{"username":"viewer","password":"viewer123"}')"
if [[ "$code" == "200" ]]; then
  echo "  OK  api v1 login ($code)"
  pass=$((pass + 1))
else
  echo "  FAIL api v1 login ($code)"
  fail=$((fail + 1))
fi

echo
echo "==> RBAC on remediation"
check "remediation pending without token" "http://localhost:8032/remediations/pending" 401
check "remediation pending with operator" "http://localhost:8032/remediations/pending" 200 "$AH"

VIEWER_TOKEN="$(auth_login viewer viewer123)"
VH="Authorization: Bearer ${VIEWER_TOKEN}"
check "viewer can read pending" "http://localhost:8032/remediations/pending" 200 "$VH"

echo
echo "==> Incident auth + versioning"
check "incidents without token" "http://localhost:8000/incidents" 401
check "incidents with token" "http://localhost:8000/incidents?page_size=1" 200 "$AH"
check "api v1 incidents" "http://localhost:8000/api/v1/incidents?page_size=1" 200 "$AH"

echo
echo "==> Observability + dashboard"
check "jaeger UI" "http://localhost:16686/"
check "dashboard health" "http://localhost:8050/health"
check "auth via dashboard proxy" "http://localhost:8050/proxy/auth/health"

echo
echo "Passed: $pass  Failed: $fail"
[[ "$fail" -eq 0 ]]
