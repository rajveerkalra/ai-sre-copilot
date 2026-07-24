#!/usr/bin/env bash
# Validate Phase 4 — knowledge + investigation (+ optional Ollama)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0
fail=0

check() {
  local name="$1"
  local url="$2"
  local expect="${3:-200}"
  code="$(curl -s -o /dev/null -w '%{http_code}' "$url" || echo 000)"
  if [[ "$code" == "$expect" ]]; then
    echo "  OK  $name ($code)"
    pass=$((pass + 1))
  else
    echo "  FAIL $name (got $code, want $expect) — $url"
    fail=$((fail + 1))
  fi
}

echo "==> Phase 4 health"
check "knowledge health" "http://localhost:8030/health"
check "knowledge ready" "http://localhost:8030/ready"
check "model-gateway health" "http://localhost:8040/health"
check "model-gateway ready" "http://localhost:8040/ready"
check "embedding-gateway health" "http://localhost:8041/health"
check "embedding-gateway ready" "http://localhost:8041/ready"
check "investigation health" "http://localhost:8031/health"
check "investigation ready" "http://localhost:8031/ready"
check "knowledge metrics" "http://localhost:8030/metrics"
check "investigation metrics" "http://localhost:8031/metrics"
check "model-gateway metrics" "http://localhost:8040/metrics"
check "embedding-gateway metrics" "http://localhost:8041/metrics"
check "ollama tags" "http://localhost:11434/api/tags"

echo
echo "==> Knowledge seed / search"
docs="$(curl -sf http://localhost:8030/documents)"
count="$(echo "$docs" | python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))")"
if [[ "$count" -ge 5 ]]; then
  echo "  OK  seeded documents ($count)"
  pass=$((pass + 1))
else
  echo "  FAIL seeded documents ($count < 5)"
  fail=$((fail + 1))
fi

search="$(curl -sf -X POST http://localhost:8030/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"high error rate 5xx","top_k":3}')"
hits="$(echo "$search" | python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))")"
if [[ "$hits" -ge 1 ]]; then
  echo "  OK  semantic search hits=$hits"
  pass=$((pass + 1))
else
  echo "  FAIL semantic search returned 0 hits"
  fail=$((fail + 1))
fi

echo
echo "==> End-to-end investigate (uses open incident if present)"
INCIDENT_ID="$(curl -sf 'http://localhost:8000/incidents?status=open&page_size=1' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); items=d.get('items') or d.get('incidents') or []; print(items[0]['id'] if items else '')" 2>/dev/null || true)"

if [[ -z "$INCIDENT_ID" ]]; then
  echo "  WARN no open incident — creating via Alertmanager-shaped webhook"
  curl -sf -X POST http://localhost:8000/webhooks/alertmanager \
    -H 'Content-Type: application/json' \
    -d '{
      "receiver":"incident-engine",
      "status":"firing",
      "alerts":[{
        "status":"firing",
        "labels":{"alertname":"HighErrorRate","severity":"critical","service":"sample-app","namespace":"default"},
        "annotations":{"summary":"High error rate on sample-app","description":"error_rate elevated"},
        "startsAt":"2026-07-24T00:00:00Z",
        "fingerprint":"phase4-validation-fingerprint"
      }]
    }' >/dev/null || true
  sleep 2
  INCIDENT_ID="$(curl -sf 'http://localhost:8000/incidents?status=open&page_size=1' \
    | python3 -c "import sys,json; d=json.load(sys.stdin); items=d.get('items') or d.get('incidents') or []; print(items[0]['id'] if items else '')")"
fi

if [[ -z "$INCIDENT_ID" ]]; then
  echo "  FAIL could not obtain incident id"
  fail=$((fail + 1))
else
  echo "  Using incident $INCIDENT_ID"
  curl -sf -X POST "http://localhost:8020/incidents/$INCIDENT_ID/collect" \
    -H 'Content-Type: application/json' -d '{"force":true}' >/dev/null || true
  sleep 2
  INV_JSON="$(curl -sf -X POST "http://localhost:8031/incidents/$INCIDENT_ID/investigate" \
    -H 'Content-Type: application/json' -d '{}')"
  INV_ID="$(echo "$INV_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('investigation_id',''))")"
  ROOT="$(echo "$INV_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('root_cause',''))")"
  CONF="$(echo "$INV_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('confidence'))")"
  if [[ -n "$INV_ID" && -n "$ROOT" ]]; then
    echo "  OK  investigation $INV_ID root_cause='$ROOT' confidence=$CONF"
    pass=$((pass + 1))
    RCA="$(curl -sf "http://localhost:8031/investigations/$INV_ID/rca")"
    EIDS="$(echo "$RCA" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('evidence_ids') or []))")"
    if [[ "$EIDS" -ge 0 ]]; then
      echo "  OK  rca evidence_ids=$EIDS"
      pass=$((pass + 1))
    fi
  else
    echo "  FAIL investigation response: $INV_JSON"
    fail=$((fail + 1))
  fi
fi

echo
echo "Passed: $pass  Failed: $fail"
[[ "$fail" -eq 0 ]]
