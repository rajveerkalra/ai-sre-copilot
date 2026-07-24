# System Architecture

End-to-end AI-Augmented SRE Copilot — local-first, Kubernetes-ready.

```mermaid
flowchart TB
  subgraph Triggers["Trigger & Observability"]
    SA[sample-app :8080]
    PROM[Prometheus]
    AM[Alertmanager]
    LOKI[Loki]
    SA --> PROM
    PROM --> AM
    SA --> LOKI
  end

  subgraph Core["Incident → Context → AI"]
    INC[incident-service :8000]
    CTX[context-service :8020]
    KNOW[knowledge-service :8030]
    INV[investigation-service :8031]
    MGW[model-gateway :8040]
    EGW[embedding-gateway :8041]
    OLL[Ollama]
    AM -->|webhook| INC
    INC -->|collect| CTX
    CTX --> PROM
    CTX --> LOKI
    INV --> CTX
    INV --> KNOW
    INV --> MGW
    KNOW --> EGW
    MGW --> OLL
  end

  subgraph Action["Remediation & UI"]
    REM[remediation-service :8032]
    AUTH[auth-service :8060]
    UI[executive-dashboard :8050]
    INV -->|RCA| REM
    REM -->|approve/execute| SA
    UI --> AUTH
    UI --> INC
    UI --> INV
    UI --> REM
  end

  subgraph Platform["Hardening & Ops"]
    PG[(Postgres)]
    REDIS[(Redis)]
    OTEL[OTel Collector]
    JAEG[Jaeger]
    INC --> PG
    CTX --> PG
    INV --> PG
    REM --> PG
    MGW --> REDIS
    INC --> OTEL
    REM --> OTEL
    AUTH --> OTEL
    OTEL --> JAEG
  end
```

## Design invariants

1. **Evidence-cited RCA** — root causes reference evidence IDs; rule fallback if LLM fails.
2. **No automatic remediation** — propose → human approve → execute.
3. **Local-first** — full loop on Docker Compose; Helm/Kustomize for cluster parity.
4. **Auth on the human path** — JWT/RBAC for APIs; Alertmanager webhooks remain open.

See also: [sequences](sequences.md), [API index](API.md), [production deploy](PRODUCTION_DEPLOYMENT.md).
