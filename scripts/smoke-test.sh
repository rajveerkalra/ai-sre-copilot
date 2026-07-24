#!/usr/bin/env bash
# Smoke-test Phase 1–7 stack
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

AH=""
if curl -sf http://localhost:8060/ready >/dev/null 2>&1; then
  AH="$(auth_header operator operator123 2>/dev/null || true)"
fi

echo "==> Phase 1–7 health checks"
check "sample-app health" "http://localhost:8080/healthz"
check "sample-app metrics" "http://localhost:8080/metrics"
check "incident-service health" "http://localhost:8000/health"
check "incident-service ready" "http://localhost:8000/ready"
check "context-service health" "http://localhost:8020/health"
check "context-service ready" "http://localhost:8020/ready"
check "context-service metrics" "http://localhost:8020/metrics"
check "knowledge-service health" "http://localhost:8030/health"
check "knowledge-service ready" "http://localhost:8030/ready"
check "model-gateway health" "http://localhost:8040/health"
check "model-gateway ready" "http://localhost:8040/ready"
check "embedding-gateway health" "http://localhost:8041/health"
check "embedding-gateway ready" "http://localhost:8041/ready"
check "investigation-service health" "http://localhost:8031/health"
check "investigation-service ready" "http://localhost:8031/ready"
check "investigation-service metrics" "http://localhost:8031/metrics"
check "remediation-service health" "http://localhost:8032/health"
check "remediation-service ready" "http://localhost:8032/ready"
check "executive-dashboard health" "http://localhost:8050/health"
check "executive-dashboard ready" "http://localhost:8050/ready"
check "auth-service health" "http://localhost:8060/health"
check "auth-service ready" "http://localhost:8060/ready"
check "jaeger UI" "http://localhost:16686/"
if [[ -n "$AH" ]]; then
  check "incident list (auth)" "http://localhost:8000/incidents" 200 "$AH"
else
  check "incident list" "http://localhost:8000/incidents"
fi
check "prometheus healthy" "http://localhost:9090/-/healthy"
check "alertmanager healthy" "http://localhost:9093/-/healthy"
check "loki ready" "http://localhost:3100/ready"
check "grafana health" "http://localhost:3000/api/health"

echo
echo "==> Prometheus targets"
curl -sf http://localhost:9090/api/v1/targets | python3 -c "
import sys, json
d=json.load(sys.stdin)
active=d['data']['activeTargets']
ok=sum(1 for t in active if t['health']=='up')
print(f'  {ok}/{len(active)} targets up')
for t in active:
    print(f\"    {t['labels'].get('job','?'):20} {t['health']:6} {t['labels'].get('instance','')}\")
"

echo
echo "==> Postgres reachable via incident-service /ready"
curl -sf http://localhost:8000/ready | python3 -m json.tool

echo
echo "Passed: $pass  Failed: $fail"
[[ "$fail" -eq 0 ]]
