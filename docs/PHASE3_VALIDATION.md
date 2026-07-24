# Phase 3 Manual Validation

## 1. Start stack

```bash
./scripts/up.sh
./scripts/smoke-test.sh
```

Expect `context-service` healthy on `:8020` and Prometheus scraping it.

## 2. Create an incident (triggers collection)

```bash
curl -s -X POST http://localhost:8000/webhooks/alertmanager \
  -H 'Content-Type: application/json' \
  -d '{
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
      "startsAt": "2026-07-24T12:00:00Z",
      "endsAt": "0001-01-01T00:00:00Z"
    }]
  }' | python3 -m json.tool
```

Capture `incident_id` from `results[0].incident_id`.

## 3. Wait for async collection (~5–30s), then fetch context

```bash
INCIDENT_ID=<uuid>
sleep 10
curl -s "http://localhost:8020/incidents/$INCIDENT_ID/context" | python3 -m json.tool | head -80
```

Expect `status` of `completed` or `partial` (partial is OK without Kind).

## 4. Section APIs

```bash
curl -s "http://localhost:8020/incidents/$INCIDENT_ID/metrics" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['metrics'].get('available'), list((d['metrics'].get('series') or {}).keys())[:5])"
curl -s "http://localhost:8020/incidents/$INCIDENT_ID/logs" | python3 -c "import sys,json; d=json.load(sys.stdin); print('lines', d['logs'].get('total_lines'))"
curl -s "http://localhost:8020/incidents/$INCIDENT_ID/deployment" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['deployment'].get('summary'))"
curl -s "http://localhost:8020/incidents/$INCIDENT_ID/system" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['system'].get('summary'))"
curl -s "http://localhost:8020/incidents/$INCIDENT_ID/kubernetes" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['kubernetes'].get('available'), d['kubernetes'].get('reason'))"
```

## 5. Manual re-collect

```bash
curl -s -X POST "http://localhost:8020/incidents/$INCIDENT_ID/collect" \
  -H 'Content-Type: application/json' \
  -d '{"force": true}' | python3 -m json.tool
```

## 6. Unit tests

```bash
cd services/context-service && pytest -q
cd ../incident-service && pytest -q
```

## Exit criteria

- [ ] context-service healthy in Compose
- [ ] Incident create schedules collection
- [ ] `GET .../context` returns normalized JSON with metrics/logs/k8s/deployment/system
- [ ] Collector failure does not fail entire run (`partial` allowed)
- [ ] Prometheus scrapes `collector_*` metrics
- [ ] Unit tests pass

Confirm to proceed to **Phase 4 (AI Investigation)**.
