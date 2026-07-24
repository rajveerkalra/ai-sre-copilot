# LinkedIn post (draft)

I built an **AI-Augmented SRE Copilot** you can run on a laptop — and package for Kubernetes without needing a cloud bill.

**What it does**
Alertmanager fires → incidents with timelines → context collectors gather metrics/logs → LangGraph investigation produces an **evidence-cited RCA** → remediation proposals wait for a **human approval** before anything executes.

**Why I care**
AI in ops is only useful if it’s grounded and gated. This project enforces citations, rule fallbacks when the LLM is down, JWT/RBAC, audit logs, and OpenTelemetry traces.

**Stack highlights**
Python/FastAPI · React · Postgres · Prometheus/Grafana/Loki · Ollama via model gateway · Helm/Kustomize/GitOps skeletons · Terraform Kind

Happy to walk through the demo script or architecture diagrams — link in comments / portfolio.

#SRE #PlatformEngineering #AIOps #OpenTelemetry #Kubernetes #BuildInPublic
