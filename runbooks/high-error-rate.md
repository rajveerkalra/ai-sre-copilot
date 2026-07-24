# High Error Rate — Sample App

## Symptoms
- Elevated `http_requests_total{status_code=~"5.."}`
- Alert: `SampleAppHighErrorRate`
- Logs: `event="order_create_failed"` or `products_list_failed`

## Immediate checks
1. Grafana → Sample App — Incident Overview
2. Loki: `{service="sample-app"} |= "error"`
3. Confirm whether fault injection is active: `GET /faults`

## Likely causes (demo)
- `error_storm` fault activated via `/faults/error_storm/activate`
- Bad deploy (Phase 3+ will correlate with deployment history)

## Mitigation
```bash
curl -X POST http://localhost:8080/faults/error_storm/deactivate
# or
./scripts/simulate-incident.sh clear
```
