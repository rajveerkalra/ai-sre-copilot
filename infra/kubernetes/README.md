# Raw Kubernetes manifests (Phase 8)

Prefer the Helm chart for full platform installs. This Kustomize base ships the
core control-plane apps (auth, incident, remediation, dashboard) with Ingress,
HPA, and NetworkPolicies for GitOps / `kubectl apply -k` workflows.

```bash
kubectl apply -k infra/kubernetes/overlays/local
```

Full stack (knowledge, investigation, gateways, postgres): use Helm.
