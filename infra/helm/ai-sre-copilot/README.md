# AI SRE Copilot Helm chart (Phase 8)

## Install (kind / local)

```bash
# Build images into the cluster (kind load / minikube image load) first
helm upgrade --install ai-sre ./infra/helm/ai-sre-copilot \
  --namespace ai-sre-copilot \
  --create-namespace \
  -f infra/helm/ai-sre-copilot/values.yaml
```

## Cost notes

Default `requests` are intentionally small so a laptop Kind cluster can schedule
the full platform. Raise `limits`/`requests` and HPA maxReplicas for prod via
`values-prod.yaml`.

## Secrets

Override `secrets.*` with Sealed Secrets / External Secrets — do not commit
production values.
