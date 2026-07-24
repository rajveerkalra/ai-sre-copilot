# Interview talking points

## Elevator pitch (30–45s)

“I built an AI SRE copilot that runs fully locally. Alerts become incidents, collectors build investigation context, a LangGraph workflow proposes an evidence-cited root cause, and remediations only execute after an explicit human approval. It’s hardened with JWT/RBAC and OpenTelemetry, and packaged with Helm so you can show the same system on Kubernetes without paying for a cloud account.”

## Architecture deep-dive prompts

| Question | Point to |
|----------|----------|
| How do you prevent LLM hallucinations? | Evidence IDs required; fallback rules; knowledge citations |
| Why not auto-remediate? | Blast radius; approval + audit + dry-run for risky actions |
| How do services talk safely? | JWT for humans; `X-Service-Token` for mesh; webhooks isolated |
| What if Ollama is down? | model-gateway circuit breaker → investigation rule fallback |
| How would you run this in prod? | Helm values-prod, ExternalSecrets, managed Postgres, GitOps |
| Cost / efficiency? | Small K8s requests, HPA caps, local-first demo path |

## Trade-offs you can discuss honestly

- HS256 shared JWT secret is fine for Compose; prod should use OIDC/JWKS.
- In-cluster Postgres is for demos; managed DB for production.
- MTTD in the UI is a proxy signal, not full detection instrumentation.
- Phase 8 Terraform creates Kind, not EKS — intentional zero cloud spend.

## Demo failure recovery

If investigate is slow: show prior RCA or fallback path.  
If no open incident: run `simulate-incident.sh`.  
If auth fails: confirm `JWT_SECRET` matches across auth/incident/remediation.

## STAR story skeleton

**Situation:** Ops teams drown in alerts; AI tools invent causes.  
**Task:** Build a trustworthy, demoable SRE assistant.  
**Action:** Modular services, evidence gate, human approval, observability, K8s packaging.  
**Result:** Full local loop + portfolio artifacts (diagrams, demo script, Helm) ready for interviews.
