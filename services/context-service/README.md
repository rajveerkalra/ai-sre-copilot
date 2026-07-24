# Context Service — Phase 3

Automated evidence collection for open incidents. Acts as a junior SRE that
gathers metrics, logs, Kubernetes state, deployment history, and system signals
into a **normalized Investigation Context** for Phase 4 AI investigation.

## Architecture

```
Alertmanager → Incident Service ──(on create)──▶ Context Service
                                                    │
                    ┌───────────────────────────────┼───────────────────────────────┐
                    ▼               ▼               ▼               ▼               ▼
              Metrics          Logs           Kubernetes      Deployment        System
            (Prometheus)      (Loki)         (Kind/EKS)      (RS/Compose)     (Docker)
                    │               │               │               │               │
                    └───────────────┴───────────────┴───────────────┴───────────────┘
                                              ▼
                               Normalized Investigation Context
                                              ▼
                                         PostgreSQL
```

## Collectors

| Collector | Source | Notes |
|-----------|--------|-------|
| metrics | Prometheus | rate, errors, latency, CPU/mem, trends vs hour/day |
| logs | Loki | last N lines, ERROR/WARN, top messages, timeline |
| kubernetes | kubeconfig / in-cluster | pods, events, CrashLoop, OOMKilled; soft-fails without cluster |
| deployment | K8s RS + Docker Compose | rollout history, images, deployment-before-incident |
| system | host + Docker socket | container health, restarts, host mem/disk |

Failed collectors are retried **3×** with exponential backoff. One failure never
aborts the whole run (`status=partial`).

## APIs

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/incidents/{id}/collect` | Trigger collection |
| GET | `/incidents/{id}/context` | Full normalized context |
| GET | `/incidents/{id}/metrics` | Metrics slice |
| GET | `/incidents/{id}/logs` | Logs slice |
| GET | `/incidents/{id}/kubernetes` | K8s slice |
| GET | `/incidents/{id}/deployment` | Deployment slice |
| GET | `/incidents/{id}/system` | System slice |
| GET | `/health` `/live` `/ready` | Probes |
| GET | `/metrics` | Prometheus metrics |

## Local tests

```bash
cd services/context-service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## Kind (optional)

Mount a kubeconfig to enable live Kubernetes collection:

```yaml
# docker-compose override example
services:
  context-service:
    environment:
      KUBECONFIG_PATH: /kube/config
    volumes:
      - ${HOME}/.kube/config:/kube/config:ro
```
