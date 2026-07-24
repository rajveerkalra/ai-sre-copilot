# Production Deployment Guide (Phase 8)

## Paths

| Path | When to use |
|------|-------------|
| **Docker Compose** | Laptop demo (Phases 1–7) |
| **Helm on Kind** | Local Kubernetes parity |
| **Helm + Argo CD / Flux** | GitOps to staging/prod |
| **Terraform Kind** | Reproducible local cluster bootstrap |

## 1. Build images

```bash
docker compose build auth-service incident-service remediation-service \
  executive-dashboard context-service knowledge-service investigation-service \
  model-gateway embedding-gateway sample-app
```

## 2. Kind cluster

```bash
cd infra/terraform
terraform init
terraform apply -auto-approve
# or: kind create cluster --name ai-sre-copilot
```

Load images:

```bash
for img in auth-service:phase7 incident-service:phase2 remediation-service:phase5 \
  executive-dashboard:phase6 context-service:phase3 knowledge-service:phase4 \
  investigation-service:phase4 model-gateway:phase4 embedding-gateway:phase4 \
  sample-app:phase1; do
  kind load docker-image "ai-sre-copilot/$img" --name ai-sre-copilot
done
```

## 3. Ingress controller

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl -n ingress-nginx rollout status deployment/ingress-nginx-controller
```

## 4. Install platform

```bash
helm upgrade --install ai-sre infra/helm/ai-sre-copilot \
  --namespace ai-sre-copilot --create-namespace
```

Production:

```bash
helm upgrade --install ai-sre infra/helm/ai-sre-copilot \
  -n ai-sre-copilot -f infra/helm/ai-sre-copilot/values-prod.yaml \
  --set secrets.create=false
```

## 5. Verify

```bash
kubectl -n ai-sre-copilot get pods,svc,hpa,ingress,networkpolicy
kubectl -n ai-sre-copilot port-forward svc/executive-dashboard 8050:8050
```

Login: `operator` / `operator123` (change before shared environments).

## 6. GitOps

Point Argo CD / Flux at this repo (`infra/gitops/*`). Replace `EXAMPLE` org URLs.

## Cost controls

- Keep `requests` low; set `limits` to protect neighbors
- Cap HPA `maxReplicas`
- Prefer managed Postgres in cloud instead of in-cluster StatefulSet for prod
- Disable unused apps via `apps.<name>.enabled=false`
