# Phase 6 — Executive Dashboard

Polished React console for demos and day-to-day SRE workflows.

```
Browser → executive-dashboard (:8050)
            ├─ /proxy/incident      → incident-service
            ├─ /proxy/context       → context-service
            ├─ /proxy/investigation → investigation-service
            └─ /proxy/remediation   → remediation-service
```

## Screens

1. **Overview** — executive KPIs (open incidents, MTTR, MTTD signal, queue depth), alert trends, AI confidence
2. **Incidents** — list + filters
3. **Incident detail** — timeline, RCA, evidence, investigation graph, remediations
4. **Remediation queue** — approve / reject (execute from detail after approve)

## Hard rules preserved

- Remediations never auto-execute
- Approvals require an operator name (sidebar)

## Out of scope

- JWT / RBAC (Phase 7)
- OpenTelemetry / secrets management (Phase 7)
