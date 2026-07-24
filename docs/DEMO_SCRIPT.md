# Live Demo Script (~12–15 minutes)

Use this for interviews, portfolio walkthroughs, or stakeholder demos.

## Prep (before audience joins)

```bash
cp .env.example .env   # if needed
./scripts/up.sh
./scripts/smoke-test.sh
# Optional: docker compose exec ollama ollama pull llama3.2
```

Open tabs:

| Tab | URL |
|-----|-----|
| Dashboard | http://localhost:8050/login |
| Grafana | http://localhost:3000 |
| Jaeger | http://localhost:16686 |
| Terminal | project root |

Login: `operator` / `operator123`.

## Narrative beats

### 1. Hook (1 min)

> “This is a local-first AI SRE copilot: alerts become incidents, AI proposes an evidence-cited RCA, and remediations never run without a human.”

Show README architecture mermaid or `docs/architecture.md`.

### 2. Observability (2 min)

- Grafana → sample-app dashboard / executive health.
- Optionally: `./scripts/simulate-incident.sh error_storm 180` and show Prometheus firing.

### 3. Incident engine (2 min)

```bash
source scripts/lib/auth.sh
AH="$(auth_header operator operator123)"
curl -s -H "$AH" 'http://localhost:8000/incidents?status=open&page_size=3' | jq
```

Show dedup (`occurrence_count`) and timeline in the dashboard.

### 4. Context + investigation (3 min)

From UI or CLI:

```bash
ID=... # open incident
curl -s -X POST -H "$AH" "http://localhost:8020/incidents/$ID/collect" | jq '.status'
curl -s -X POST "http://localhost:8031/incidents/$ID/investigate" -H 'Content-Type: application/json' -d '{}' | jq
```

Open incident detail → **RCA report** + **Evidence** + investigation graph.

Call out: *evidence IDs* and *fallback if Ollama is cold*.

### 5. Remediation gate (3 min)

- Propose remediations → queue shows `proposed`.
- Attempt execute without approve → **409**.
- Approve → Execute `clear_fault` → sample-app recovers.
- Timeline events: `remediation_proposed|approved|executed`.

### 6. Hardening & cloud readiness (2 min)

- JWT 401 without token; Jaeger traces; `./scripts/validate-phase8.sh` or show Helm chart tree.
- “Compose for demo, Helm/GitOps for cluster — no cloud bill required for the portfolio.”

### 7. Close (1 min)

> “Human-in-the-loop by design. Evidence-backed AI. Production packaging without cloud spend.”

Point to resume bullets / interview talking points in `docs/portfolio/`.

## Automated companion

```bash
./scripts/demo.sh
```

## Recording a GIF / video

See [docs/demo/RECORDING.md](demo/RECORDING.md).
