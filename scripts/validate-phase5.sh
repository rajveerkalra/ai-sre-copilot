#!/usr/bin/env bash
# Validate Phase 5 — remediation propose → approve → execute
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
  code="$(curl -s -o /dev/null -w '%{http_code}' -H "$AH" "$url" || echo 000)"
  if [[ "$code" == "$expect" ]]; then
    echo "  OK  $name ($code)"
    pass=$((pass + 1))
  else
    echo "  FAIL $name (got $code, want $expect) — $url"
    fail=$((fail + 1))
  fi
}

echo "==> Phase 5 health"
check "remediation health" "http://localhost:8032/health"
check "remediation ready" "http://localhost:8032/ready"
check "remediation metrics" "http://localhost:8032/metrics"

echo
echo "==> Propose / approve / execute"
INCIDENT_ID="$(curl -sf -H "$AH" 'http://localhost:8000/incidents?status=open&page_size=1' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); items=d.get('items') or []; print(items[0]['id'] if items else '')" 2>/dev/null || true)"

if [[ -z "$INCIDENT_ID" ]]; then
  echo "  FAIL no open incident"
  fail=$((fail + 1))
else
  echo "  Using incident $INCIDENT_ID"
  curl -sf -X POST "http://localhost:8031/incidents/$INCIDENT_ID/investigate" \
    -H 'Content-Type: application/json' -d '{}' >/dev/null || true

  PROP_JSON="$(curl -sf -X POST -H "$AH" "http://localhost:8032/incidents/$INCIDENT_ID/remediations/propose")"
  COUNT="$(echo "$PROP_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))")"
  if [[ "$COUNT" -ge 1 ]]; then
    echo "  OK  proposed count=$COUNT"
    pass=$((pass + 1))
  else
    echo "  FAIL propose returned count=$COUNT"
    fail=$((fail + 1))
  fi

  PID="$(echo "$PROP_JSON" | python3 -c "
import sys,json
props=json.load(sys.stdin).get('proposals') or []
clear=[p for p in props if p.get('action_type')=='clear_fault']
print((clear or props)[0]['id'] if props else '')
")"

  if [[ -n "$PID" ]]; then
    code="$(curl -s -o /dev/null -w '%{http_code}' -X POST -H "$AH" \
      "http://localhost:8032/remediations/$PID/execute" \
      -H 'Content-Type: application/json' -d '{}')"
    if [[ "$code" == "409" ]]; then
      echo "  OK  execute without approve blocked ($code)"
      pass=$((pass + 1))
    else
      echo "  FAIL expected 409 without approve, got $code"
      fail=$((fail + 1))
    fi

    curl -sf -X POST -H "$AH" "http://localhost:8032/remediations/$PID/approve" \
      -H 'Content-Type: application/json' \
      -d '{"approved_by":"phase5-validator","comment":"demo"}' >/dev/null
    EXEC="$(curl -sf -X POST -H "$AH" "http://localhost:8032/remediations/$PID/execute" \
      -H 'Content-Type: application/json' \
      -d '{"dry_run":false,"actor":"phase5-validator"}')"
    STATUS="$(echo "$EXEC" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))")"
    if [[ "$STATUS" == "succeeded" ]]; then
      echo "  OK  execute status=$STATUS"
      pass=$((pass + 1))
    else
      echo "  FAIL execute status=$STATUS body=$EXEC"
      fail=$((fail + 1))
    fi

    TL="$(curl -sf -H "$AH" "http://localhost:8000/incidents/$INCIDENT_ID/timeline")"
    HAS="$(echo "$TL" | python3 -c "
import sys,json
ev=json.load(sys.stdin)
types=[e.get('event_type') for e in ev]
print('yes' if 'remediation_proposed' in types and 'remediation_approved' in types else 'no')
")"
    if [[ "$HAS" == "yes" ]]; then
      echo "  OK  timeline has remediation events"
      pass=$((pass + 1))
    else
      echo "  FAIL timeline missing remediation events"
      fail=$((fail + 1))
    fi
  fi
fi

echo
echo "Passed: $pass  Failed: $fail"
[[ "$fail" -eq 0 ]]
