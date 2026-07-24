# Resume bullets

Copy/adapt to your voice. Quantify with your own metrics when possible.

## Short (3 bullets)

- Built a **local-first AI SRE Copilot** (Python/FastAPI, React, Docker Compose) that turns Alertmanager alerts into incidents, runs **evidence-cited RCA** via LangGraph + model gateway (with rule fallback), and enforces **human-approved remediations** (no auto-execute).
- Delivered production hardening: **JWT/RBAC**, structured audit logs, **OpenTelemetry → Jaeger**, rate limiting, backup/restore, and API versioning across microservices.
- Packaged for cloud without cloud spend: **Helm** (Ingress, HPA, NetworkPolicies), Kustomize, Argo CD/Flux GitOps skeletons, and Terraform Kind bootstrap.

## Extended (5–7 bullets)

- Designed a modular SRE platform: observability (Prometheus/Grafana/Loki), incident engine with fingerprint dedup + timelines, context collectors, vector runbook search, multi-agent investigation, remediation engine, and executive dashboard.
- Implemented **anti-hallucination** controls: RCA must cite evidence IDs; LLM calls route through model/embedding gateways with retries, circuit breakers, and Redis caching.
- Built a React executive UI for KPIs (MTTR/MTTD proxies, alert trends, AI confidence), investigation graph, evidence viewer, and remediation approval queue.
- Added enterprise controls: shared JWT secret + service mesh token, role permissions (viewer/operator/admin), OTLP tracing, secrets templates, DR docs, and security review checklist.
- Authored Kubernetes packaging with cost-aware resource requests/limits and HPA so a laptop Kind cluster can demonstrate production topology.

## Skills keywords

`SRE` · `Platform Engineering` · `FastAPI` · `LangGraph` · `OpenTelemetry` · `Prometheus` · `Docker` · `Helm` · `RBAC` · `Incident Management` · `Human-in-the-loop AI`
