# Security Review Checklist (Phase 7)

## Authentication & authorization

- [x] JWT HS256 with shared secret (rotate via `JWT_SECRET`)
- [x] RBAC roles: viewer / operator / admin
- [x] Service mesh token for internal calls (`X-Service-Token`)
- [x] Webhooks intentionally unauthenticated (Alertmanager); protect at network layer in prod
- [ ] Replace demo passwords before any shared environment
- [ ] Prefer RS256/JWKS + IdP (OIDC) for multi-tenant prod

## Secrets

- [x] `secrets/` gitignored for real files
- [x] Example template only in git
- [ ] No secrets in images or CI logs
- [ ] Use Docker/K8s secrets or a vault in production

## Abuse controls

- [x] Login rate limiting
- [x] Remediation mutate rate limiting
- [ ] WAF / ingress rate limits at edge

## Observability & audit

- [x] Structured audit events (`audit=true` logs)
- [x] Request IDs on HTTP middleware
- [x] OTLP traces → Jaeger
- [ ] Retain audit logs outside container stdout in prod

## Data

- [x] Postgres backup/restore scripts
- [ ] Encrypt backups at rest
- [ ] Document data classification (incident payloads may contain PII)

## Explicit non-goals (later)

- Full IdP federation, mTLS service mesh, network policies (Phase 8)
