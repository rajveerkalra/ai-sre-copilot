# Screenshot checklist

Capture these for README / LinkedIn / interviews. Save under `docs/demo/media/`
(gitignored) or attach externally.

| # | Shot | How |
|---|------|-----|
| 1 | Dashboard overview KPIs | http://localhost:8050 — Overview |
| 2 | Incident timeline | Incident detail → Timeline tab |
| 3 | RCA report | Detail → RCA (confidence + next steps) |
| 4 | Evidence viewer | Detail → Evidence (metrics/logs JSON) |
| 5 | Investigation graph | Detail header pipeline nodes |
| 6 | Remediation queue | http://localhost:8050/remediations |
| 7 | Grafana sample-app | http://localhost:3000 |
| 8 | Jaeger traces | http://localhost:16686 — search `incident-service` |
| 9 | OpenAPI (auth or remediation) | http://localhost:8060/docs |
| 10 | Helm tree | `tree infra/helm/ai-sre-copilot` in terminal |

## README embeds

Once files exist:

```markdown
![Overview](docs/demo/media/01-overview.png)
```

Until then, diagrams in [architecture.md](architecture.md) render on GitHub via Mermaid.
