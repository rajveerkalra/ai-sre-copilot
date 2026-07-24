# Executive Dashboard (Phase 6)

React UI for incidents, RCA, evidence, KPIs, and the remediation approval queue.

**URL:** http://localhost:8050

## Features

| Area | What you get |
|------|----------------|
| Login | JWT via auth-service (`/login`) |
| Overview | Open count, MTTR, MTTD proxy, remediation queue depth, alert trends, AI confidence |
| Incidents | Filterable list → detail |
| Detail | Timeline, RCA report, evidence viewer, investigation graph, propose/approve/execute |
| Remediation queue | Pending approvals with operator identity |

Demo users: `operator` / `operator123` (also admin, viewer — see Phase 7 docs).

## Local development

```bash
cd services/executive-dashboard
npm install
npm run dev
```

Vite proxies `/proxy/*` to local backend ports (8000/8020/8031/8032).

## Docker

Built and served via nginx in Compose (`executive-dashboard` on port 8050).
The container proxies API calls to internal service DNS names.

## Operator identity

Set the operator name in the sidebar (stored in `localStorage`). Approvals and
executions send that name to remediation-service.
