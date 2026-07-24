# Phase 4 — AI Investigation Engine

## Objective

Build an enterprise investigation platform that reasons **only from collected
evidence**. No memory-based answers. Every RCA cites evidence IDs.

## Knowledge base

ChromaDB indexes runbooks; vectors come from **embedding-gateway** (default ONNX
MiniLM). Knowledge Service never loads ONNX / Sentence Transformers locally.
Seeded from `runbooks/` plus `services/knowledge-service/seed/`.

## AI infrastructure

See [AI_INFRASTRUCTURE.md](AI_INFRASTRUCTURE.md) for Model Gateway, Embedding
Gateway, Redis caching, and resilience patterns.

## Services

| Service | Port | Role |
|---------|-----:|------|
| knowledge-service | 8030 | ChromaDB runbooks + semantic search |
| investigation-service | 8031 | LangGraph multi-agent RCA |
| model-gateway | 8040 | LLM provider abstraction |
| embedding-gateway | 8041 | Embedding provider abstraction |
| redis | 6379 | Search / embedding / context caches |
| ollama | 11434 | Local LLM (via model-gateway only) |

## Investigation flow

```
Start
  → Metrics Agent
  → Logs Agent
  → Kubernetes Agent
  → Runbook Agent (knowledge-service)
  → Evidence Aggregator
  → RCA Synthesizer (model-gateway or rules)
  → Citation Validator
  → Final Investigation Report
```

## Evidence model

Stable IDs produced from Phase 3 context:

| Prefix | Source |
|--------|--------|
| `metric-*` | Prometheus series |
| `log-*` | Loki aggregates |
| `k8s-*` | Kubernetes findings |
| `deploy-*` | Deployment/image changes |
| `system-*` | Host/Docker health |
| `runbook-*` | Knowledge hits |
| `incident-meta` | Alert metadata |

## Anti-hallucination

1. Agents may only reference IDs present in the evidence catalog
2. Citation validator strips unknown IDs
3. If no valid citations remain → `root_cause = "Insufficient evidence"`
4. Model gateway failures → deterministic `rule_based_rca`

## Persistence (`alembic_version_investigation`)

- `investigation_runs` — status, model, prompt version, duration, report
- `evidence` — catalog rows per run
- `agent_results` — per-agent outputs + timing
- `rca_reports` — root cause, confidence, citations, next steps

## Example

```bash
curl -s -X POST "http://localhost:8020/incidents/<INCIDENT_ID>/collect" | jq
curl -s -X POST "http://localhost:8031/incidents/<INCIDENT_ID>/investigate" | jq
curl -s "http://localhost:8031/investigations/<INV_ID>/rca" | jq
```

## Out of scope (Phase 5+)

- Remediation execution
- Approval workflows
- Executive UI
