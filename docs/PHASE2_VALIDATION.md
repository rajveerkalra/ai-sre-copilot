# Phase 2 Manual Validation

Prerequisites: Phase 1 stack patterns; Docker Compose with Postgres + incident-service.

## 1. Start the stack

```bash
cd /path/to/ai-sre-copilot
./scripts/up.sh
./scripts/smoke-test.sh
```

Expect `incident-service` and `postgres` healthy; Prometheus scraping `incident-service`.

## 2. Trigger a simulated incident

```bash
./scripts/simulate-incident.sh error_storm 180
```

Wait ~1–2 minutes for Prometheus alert evaluation + Alertmanager grouping.

## 3. Verify incident creation

```bash
curl -s 'http://localhost:8000/incidents?status=open' | python3 -m json.tool
```

Expect at least one open incident (e.g. `SampleAppHighErrorRate`).

```bash
INCIDENT_ID=$(curl -s 'http://localhost:8000/incidents?status=open' | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])")
curl -s "http://localhost:8000/incidents/$INCIDENT_ID" | python3 -m json.tool
```

## 4. Trigger the same alert again (dedup)

Keep the fault active (or re-run traffic). Alertmanager will re-notify on `repeat_interval`
or you can POST a synthetic webhook:

```bash
curl -s -X POST http://localhost:8000/webhooks/alertmanager \
  -H 'Content-Type: application/json' \
  -d @- <<'EOF' | python3 -m json.tool
{
  "status": "firing",
  "receiver": "incident-webhook",
  "alerts": [{
    "status": "firing",
    "labels": {
      "alertname": "SampleAppHighErrorRate",
      "severity": "critical",
      "service": "sample-app",
      "instance": "sample-app:8080",
      "namespace": "default",
      "pod": "sample-app-0"
    },
    "annotations": {"summary": "SampleAppHighErrorRate firing"},
    "startsAt": "2026-07-24T10:00:00Z",
    "endsAt": "0001-01-01T00:00:00Z"
  }]
}
EOF
```

POST the same payload again and confirm `action` is `deduplicated` and
`occurrence_count` increases.

```bash
curl -s "http://localhost:8000/incidents/$INCIDENT_ID" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['occurrence_count'], d['status'])"
```

## 5. Inspect timeline

```bash
curl -s "http://localhost:8000/incidents/$INCIDENT_ID/timeline" | python3 -m json.tool
```

Expect `incident_created`, `alert_received`, and one or more `alert_repeated`.

## 6. Add a note and resolve

```bash
curl -s -X POST "http://localhost:8000/incidents/$INCIDENT_ID/notes" \
  -H 'Content-Type: application/json' \
  -d '{"message":"SRE investigating error storm"}' | python3 -m json.tool

curl -s -X POST "http://localhost:8000/incidents/$INCIDENT_ID/resolve" \
  -H 'Content-Type: application/json' \
  -d '{"message":"Cleared fault injection"}' | python3 -m json.tool

./scripts/simulate-incident.sh clear
```

## 7. Confirm resolution

```bash
curl -s "http://localhost:8000/incidents/$INCIDENT_ID" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'], d['resolved_at'])"
curl -s "http://localhost:8000/incidents/$INCIDENT_ID/timeline" | python3 -c "import sys,json; print([e['event_type'] for e in json.load(sys.stdin)])"
```

## Exit criteria

- [ ] Postgres + incident-service healthy in Compose
- [ ] Alertmanager delivers to incident-service
- [ ] First alert creates an open incident
- [ ] Repeat alert deduplicates (same id, higher occurrence_count)
- [ ] Timeline contains expected event types
- [ ] Resolve API sets status=resolved and appends timeline event
- [ ] Unit tests pass: `cd services/incident-service && pytest -q`

Confirm to proceed to **Phase 3 (Context Collectors)**.
