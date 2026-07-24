# Phase 1 Manual Validation

Run after `./scripts/up.sh` succeeds.

## 1. Service health

```bash
./scripts/smoke-test.sh
```

Expect all checks OK and `sample-app` target `up`.

## 2. Metrics scrape

```bash
curl -s http://localhost:8080/metrics | grep http_requests_total
curl -s 'http://localhost:9090/api/v1/query?query=up{job="sample-app"}' | jq .
```

## 3. Structured logs → Loki

```bash
# generate a few requests
curl -s http://localhost:8080/api/products
sleep 5
curl -sG http://localhost:3100/loki/api/v1/query_range \
  --data-urlencode 'query={service="sample-app"}' \
  --data-urlencode "start=$(date -u -v-10M +%s)000000000" \
  --data-urlencode "end=$(date -u +%s)000000000" | jq '.data.result | length'
```

Expect a non-zero result count (macOS `date -v`; on Linux use `date -u -d '10 minutes ago' +%s`).

## 4. Grafana dashboards

1. Open http://localhost:3000 (admin / admin)
2. Dashboards → AI SRE Copilot
   - **Sample App — Incident Overview**
   - **Executive — Platform Health**
3. Confirm panels populate after traffic:
   ```bash
   ./scripts/generate-traffic.sh
   ```

## 5. Fault → alert → webhook

```bash
./scripts/simulate-incident.sh error_storm 120
```

Within ~2 minutes:

1. Prometheus Alerts: http://localhost:9090/alerts — `SampleAppHighErrorRate` firing
2. Alertmanager: http://localhost:9093/#/alerts
3. Webhook sink received payload:
   ```bash
   curl -s http://localhost:8000/webhooks/recent | jq '.count, .recent[0].alert_count'
   ```

## 6. Clear faults

```bash
./scripts/simulate-incident.sh clear
```

## 7. Unit tests (sample-app)

```bash
cd services/sample-app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=../..:. pytest -q
```

## Exit criteria for Phase 1

- [ ] Compose stack healthy
- [ ] Prometheus scraping sample-app
- [ ] Recording + alert rules loaded
- [ ] Loki receiving sample-app logs
- [ ] Grafana dashboards render
- [ ] Fault injection triggers alerts
- [ ] Alertmanager delivers webhooks to webhook-sink
- [ ] Sample-app unit tests pass

When all boxes are checked, confirm to proceed to **Phase 2 (Incident Engine)**.
