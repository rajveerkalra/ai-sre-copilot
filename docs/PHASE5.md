# Phase 5 — Remediation Engine

Human-approved remediations. **No automatic execution.**

## Architecture

```
Investigation RCA
       ↓
Remediation Service (:8032)
       ↓ propose
Pending proposals ──approve──▶ Execute
                 └──reject──▶ Closed
       ↓
Audit logs + Incident timeline events
```

## Action types

| Type | Local behavior |
|------|----------------|
| `clear_fault` | Calls sample-app `/faults/.../deactivate` |
| `rollback` / `scale` | Dry-run unless `ALLOW_MUTATIONS=true` |
| `restart_service` | Dry-run unless `ALLOW_COMPOSE_RESTART=true` |
| `runbook_manual` | Acknowledgement only |

## Example

```bash
ID=$(curl -s 'http://localhost:8000/incidents?status=open&page_size=1' | jq -r '.items[0].id')
curl -s -X POST "http://localhost:8032/incidents/$ID/remediations/propose" | jq
PID=$(curl -s "http://localhost:8032/remediations/pending" | jq -r '.[0].id')
curl -s -X POST "http://localhost:8032/remediations/$PID/approve" \
  -H 'Content-Type: application/json' \
  -d '{"approved_by":"sre-oncall","comment":"safe for demo"}' | jq
curl -s -X POST "http://localhost:8032/remediations/$PID/execute" \
  -H 'Content-Type: application/json' \
  -d '{"dry_run":false,"actor":"sre-oncall"}' | jq
```

## Out of scope

- JWT/RBAC (Phase 7)
- Real Kubernetes mutate APIs
