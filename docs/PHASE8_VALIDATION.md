# Phase 8 Validation

```bash
./scripts/validate-phase8.sh
```

## Checklist

- [ ] `helm lint infra/helm/ai-sre-copilot` passes
- [ ] `helm template` renders Deployments, Services, HPA, Ingress, NetworkPolicy
- [ ] `kubectl kustomize infra/kubernetes/overlays/local` succeeds
- [ ] GitOps manifests present (Argo CD + Flux)
- [ ] Terraform files present (`versions.tf`, Kind cluster resource)
- [ ] Production guide documents Kind load + Helm install path

## Optional (needs Kind)

```bash
cd infra/terraform && terraform init && terraform plan
kind load docker-image ai-sre-copilot/auth-service:phase7 --name ai-sre-copilot
helm upgrade --install ai-sre infra/helm/ai-sre-copilot -n ai-sre-copilot --create-namespace
```
