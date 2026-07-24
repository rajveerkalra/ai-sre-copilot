# Phase 8 — Kubernetes & Cloud Readiness

Cloud-native packaging **without requiring ongoing cloud spend**. Local Kind +
Helm/Kustomize/GitOps/Terraform skeletons demonstrate production deployment shape.

## Deliverables

| Area | Location |
|------|----------|
| Helm chart | [`infra/helm/ai-sre-copilot`](../infra/helm/ai-sre-copilot) |
| Kustomize base + local overlay | [`infra/kubernetes`](../infra/kubernetes) |
| Ingress + HPA + NetworkPolicies | Helm templates + k8s base |
| Argo CD Application | [`infra/gitops/argocd`](../infra/gitops/argocd) |
| Flux HelmRelease / Kustomization | [`infra/gitops/flux`](../infra/gitops/flux) |
| Terraform Kind skeleton | [`infra/terraform`](../infra/terraform) |
| Prod sizing | `values-prod.yaml` |
| Deploy guide | [`PRODUCTION_DEPLOYMENT.md`](PRODUCTION_DEPLOYMENT.md) |

## Cost-aware defaults

Requests are laptop-friendly (25–100m CPU, 64–256Mi). HPA scales auth / incident /
remediation / dashboard under load. Prod values raise floors and PVC size.

## Quick validation

```bash
./scripts/validate-phase8.sh
```

## Out of scope

- Paying for EKS/GKE/AKS (stubbed in `cloud.tf`)
- Phase 9 portfolio / demo assets
