#!/usr/bin/env bash
# Validate Phase 8 — Helm / Kustomize / GitOps / Terraform packaging
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

pass=0
fail=0

ok() { echo "  OK  $1"; pass=$((pass + 1)); }
bad() { echo "  FAIL $1"; fail=$((fail + 1)); }

echo "==> Required files"
for f in \
  infra/helm/ai-sre-copilot/Chart.yaml \
  infra/helm/ai-sre-copilot/values.yaml \
  infra/helm/ai-sre-copilot/values-prod.yaml \
  infra/helm/ai-sre-copilot/templates/deployments.yaml \
  infra/helm/ai-sre-copilot/templates/hpa.yaml \
  infra/helm/ai-sre-copilot/templates/ingress.yaml \
  infra/helm/ai-sre-copilot/templates/networkpolicy.yaml \
  infra/kubernetes/base/kustomization.yaml \
  infra/kubernetes/overlays/local/kustomization.yaml \
  infra/gitops/argocd/application.yaml \
  infra/gitops/flux/kustomization.yaml \
  infra/terraform/main.tf \
  infra/terraform/versions.tf \
  docs/PHASE8.md \
  docs/PRODUCTION_DEPLOYMENT.md
do
  if [[ -f "$f" ]]; then ok "$f"; else bad "missing $f"; fi
done

echo
echo "==> Helm"
if command -v helm >/dev/null 2>&1; then
  if helm lint infra/helm/ai-sre-copilot >/tmp/helm-lint.out 2>&1; then
    ok "helm lint"
  else
    bad "helm lint"
    cat /tmp/helm-lint.out | tail -20
  fi
  if helm template ai-sre infra/helm/ai-sre-copilot >/tmp/helm-template.yaml 2>/tmp/helm-template.err; then
    ok "helm template"
    for kind in Deployment Service HorizontalPodAutoscaler Ingress NetworkPolicy StatefulSet; do
      if grep -q "^kind: $kind$" /tmp/helm-template.yaml; then
        ok "renders $kind"
      else
        bad "missing kind $kind"
      fi
    done
    # Cost-aware requests present
    if grep -q "cpu: 25m" /tmp/helm-template.yaml; then
      ok "cost-aware cpu requests present"
    else
      bad "expected small cpu requests"
    fi
  else
    bad "helm template"
    cat /tmp/helm-template.err | tail -30
  fi
else
  echo "  SKIP helm not installed — structural checks only"
fi

echo
echo "==> Kustomize"
if command -v kubectl >/dev/null 2>&1; then
  if kubectl kustomize infra/kubernetes/overlays/local >/tmp/kust.yaml 2>/tmp/kust.err; then
    ok "kubectl kustomize overlays/local"
    if grep -q "kind: NetworkPolicy" /tmp/kust.yaml && grep -q "kind: Ingress" /tmp/kust.yaml; then
      ok "kustomize includes Ingress + NetworkPolicy"
    else
      bad "kustomize missing Ingress/NetworkPolicy"
    fi
  else
    bad "kubectl kustomize"
    cat /tmp/kust.err | tail -20
  fi
elif command -v kustomize >/dev/null 2>&1; then
  if kustomize build infra/kubernetes/overlays/local >/tmp/kust.yaml 2>/tmp/kust.err; then
    ok "kustomize build overlays/local"
  else
    bad "kustomize build"
  fi
else
  echo "  SKIP kubectl/kustomize not installed"
fi

echo
echo "Passed: $pass  Failed: $fail"
[[ "$fail" -eq 0 ]]
