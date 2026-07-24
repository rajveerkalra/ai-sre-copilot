# GitOps skeletons (Phase 8)

## Argo CD

```bash
kubectl apply -n argocd -f infra/gitops/argocd/application.yaml
```

Update `repoURL` to your fork before applying.

## Flux

```bash
kubectl apply -f infra/gitops/flux/kustomization.yaml
```

Choose **either** HelmRelease **or** Kustomization path — do not sync both to the
same workloads without careful ownership.
