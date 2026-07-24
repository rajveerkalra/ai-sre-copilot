#!/usr/bin/env bash
# Guided terminal demo — prints narrative + hits live APIs when stack is up
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck source=lib/auth.sh
source "$ROOT/scripts/lib/auth.sh"

say() { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }
pause() { sleep "${DEMO_PAUSE:-1}"; }

say "AI SRE Copilot — live demo walkthrough"
pause

say "1) Auth — obtain operator JWT"
if ! curl -sf http://localhost:8060/ready >/dev/null; then
  echo "Stack not ready. Run ./scripts/up.sh first."
  exit 1
fi
AH="$(auth_header operator operator123)"
echo "  token acquired"
pause

say "2) Open incidents"
curl -sf -H "$AH" 'http://localhost:8000/incidents?page_size=3' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"  total={d.get('total')} open_sample={[i.get('title') for i in d.get('items',[])]}\")"
INCIDENT_ID="$(curl -sf -H "$AH" 'http://localhost:8000/incidents?status=open&page_size=1' \
  | python3 -c "import sys,json; items=json.load(sys.stdin).get('items') or []; print(items[0]['id'] if items else '')")"
if [[ -z "$INCIDENT_ID" ]]; then
  echo "  No open incident — create one with ./scripts/simulate-incident.sh error_storm 120"
  echo "  Continuing with read-only checks..."
else
  echo "  Using incident $INCIDENT_ID"
  pause

  say "3) Ensure investigation exists"
  curl -sf -X POST "http://localhost:8031/incidents/$INCIDENT_ID/investigate" \
    -H 'Content-Type: application/json' -d '{}' \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"  status={d.get('status')} confidence={d.get('confidence')} fallback={d.get('used_fallback')}\")" || echo "  investigate soft-failed"
  pause

  say "4) Propose remediations (no auto-execute)"
  PROP="$(curl -sf -X POST -H "$AH" "http://localhost:8032/incidents/$INCIDENT_ID/remediations/propose")"
  echo "$PROP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"  proposals={d.get('count')}\");
[print(f\"   - {p.get('action_type')} [{p.get('status')}] {p.get('title')}\") for p in d.get('proposals') or []]"
  PID="$(echo "$PROP" | python3 -c "import sys,json; props=json.load(sys.stdin).get('proposals') or []; print(props[0]['id'] if props else '')")"
  if [[ -n "$PID" ]]; then
    pause
    say "5) Execute without approve must be blocked (409)"
    code="$(curl -s -o /dev/null -w '%{http_code}' -X POST -H "$AH" \
      "http://localhost:8032/remediations/$PID/execute" -H 'Content-Type: application/json' -d '{}')"
    echo "  HTTP $code (expect 409)"
  fi
fi

pause
say "6) Dashboard / Jaeger / Grafana"
echo "  UI:     http://localhost:8050  (operator / operator123)"
echo "  Jaeger: http://localhost:16686"
echo "  Grafana:http://localhost:3000  (admin / admin)"
echo
say "Demo script complete. Full narrative: docs/DEMO_SCRIPT.md"
