# Phase 1 — Observability Foundation

## Scope

Establish the local observability backbone that all later phases depend on:

| Component | Role | Port |
|-----------|------|------|
| sample-app | Demo FastAPI workload + fault injection | 8080 |
| webhook-sink | Temporary Alertmanager receiver (→ Incident Service in Phase 2) | 8000 |
| Prometheus | Metrics + alert/recording rules | 9090 |
| Alertmanager | Alert routing + webhooks | 9093 |
| Loki | Log aggregation | 3100 |
| Promtail | Docker log shipping | — |
| Grafana | Dashboards (incident + executive) | 3000 |

## Architecture (Phase 1)

```
                    ┌─────────────┐
   traffic/faults → │ sample-app  │──────┐
                    └──────┬──────┘      │ /metrics
                           │ logs        ▼
                           │      ┌────────────┐     rules      ┌──────────────┐
                           ▼      │ Prometheus │───────────────▶│ Alertmanager │
                      ┌────────┐ └─────┬──────┘                └──────┬───────┘
                      │Promtail│       │                              │ webhook
                      └───┬────┘       │                              ▼
                          ▼            ▼                       ┌─────────────┐
                      ┌──────┐   ┌─────────┐                   │webhook-sink │
                      │ Loki │   │ Grafana │◀── datasources ── │  (Phase 1)  │
                      └──────┘   └─────────┘                   └─────────────┘
```

## Bring-up

```bash
cp .env.example .env
./scripts/up.sh
./scripts/smoke-test.sh
```

## Simulate incidents

```bash
./scripts/simulate-incident.sh error_storm 180
./scripts/simulate-incident.sh latency 120
./scripts/simulate-incident.sh cpu_spike 90
./scripts/simulate-incident.sh clear
```

## Validation checklist

See [PHASE1_VALIDATION.md](./PHASE1_VALIDATION.md).

## Out of scope (later phases)

- Incident persistence / dedup API (Phase 2)
- Context collectors (Phase 3)
- LangGraph investigation (Phase 4)
- Remediation approval (Phase 5)
- React executive UI (Phase 6)
- JWT/RBAC/audit hardening (Phase 7)
