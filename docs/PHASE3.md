# Phase 3 — Context Collection

## Scope

Automatically gather SRE investigation evidence when an incident is created.

| Component | Role | Port |
|-----------|------|------|
| context-service | Collector orchestrator + APIs | 8020 |
| collectors | metrics, logs, k8s, deployment, system | — |

## Flow

```mermaid
sequenceDiagram
    participant AM as Alertmanager
    participant IS as Incident Service
    participant CS as Context Service
    participant Prom as Prometheus
    participant Loki as Loki
    participant DB as PostgreSQL

    AM->>IS: webhook (firing)
    IS->>IS: create incident
    IS-->>CS: POST /incidents/{id}/collect (async)
    par Collectors
        CS->>Prom: query metrics
        CS->>Loki: query logs
        CS->>CS: k8s / deploy / system
    end
    CS->>DB: store investigation_context + collector_runs
```

## Validation

See [PHASE3_VALIDATION.md](./PHASE3_VALIDATION.md).

## Out of scope

LangGraph, Ollama, ChromaDB, RCA, remediation (Phase 4+).
