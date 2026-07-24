#!/usr/bin/env bash
# Activate a demo fault scenario and optionally generate traffic
set -euo pipefail

BASE_URL="${SAMPLE_APP_URL:-http://localhost:8080}"
SCENARIO="${1:-error_storm}"
DURATION="${2:-180}"

usage() {
  cat <<EOF
Usage: $0 <scenario> [duration_seconds]

Scenarios:
  error_storm          High 5xx rate (default)
  latency              Elevated p99 latency
  cpu_spike            CPU burn
  memory_leak          Memory ballast
  dependency_timeout   Downstream timeout on orders
  clear                Deactivate all faults

Examples:
  $0 error_storm 180
  $0 latency 120
  $0 clear
EOF
}

if [[ "$SCENARIO" == "-h" || "$SCENARIO" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "$SCENARIO" == "clear" ]]; then
  curl -sf -X POST "${BASE_URL}/faults/deactivate-all" | python3 -m json.tool
  echo "All faults cleared."
  exit 0
fi

case "$SCENARIO" in
  error_storm)
    BODY='{"error_rate":0.9,"duration_seconds":'"$DURATION"'}'
    FAULT=error_storm
    ;;
  latency)
    BODY='{"min_ms":800,"max_ms":2500,"duration_seconds":'"$DURATION"'}'
    FAULT=latency
    ;;
  cpu_spike)
    BODY='{"workers":2,"duration_seconds":'"$DURATION"'}'
    FAULT=cpu_spike
    ;;
  memory_leak)
    BODY='{"megabytes":256,"duration_seconds":'"$DURATION"'}'
    FAULT=memory_leak
    ;;
  dependency_timeout)
    BODY='{"duration_seconds":'"$DURATION"'}'
    FAULT=dependency_timeout
    ;;
  *)
    echo "Unknown scenario: $SCENARIO"
    usage
    exit 1
    ;;
esac

echo "==> Activating fault: $FAULT (${DURATION}s)"
curl -sf -X POST "${BASE_URL}/faults/${FAULT}/activate" \
  -H 'Content-Type: application/json' \
  -d "$BODY" | python3 -m json.tool

echo "==> Generating traffic in background for ${DURATION}s..."
DURATION="$DURATION" RATE=3 "$(dirname "$0")/generate-traffic.sh" &
TRAFFIC_PID=$!

echo
echo "Watch:"
echo "  Grafana:      http://localhost:3000/d/sample-app-overview"
echo "  Prometheus:   http://localhost:9090/alerts"
echo "  Alertmanager: http://localhost:9093"
echo "  Webhooks:     http://localhost:8000/webhooks/recent"
echo
echo "Traffic PID: $TRAFFIC_PID (will stop after ${DURATION}s)"
wait "$TRAFFIC_PID" || true
echo "Simulation complete. Faults auto-expire after ${DURATION}s (or run: $0 clear)"
