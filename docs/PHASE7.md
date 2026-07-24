# Phase 7 — Enterprise Production Hardening

JWT/RBAC, audit events, OpenTelemetry traces, secrets hygiene, backup/restore,
API versioning, and rate limiting — without requiring a cloud account.

## Components

| Piece | Role |
|-------|------|
| **auth-service** (:8060) | Login, JWT issue, `/auth/me`, rate-limited |
| **libs/common/auth** | Shared JWT verify + RBAC permissions |
| **libs/common/otel** | OTLP trace bootstrap |
| **libs/common/audit** | Immutable structured audit log events |
| **libs/common/ratelimit** | Sliding-window limiter |
| **otel-collector** | Receives OTLP → Jaeger |
| **jaeger** (:16686) | Trace UI |
| **secrets/** | Local secret templates (not committed) |

## Demo users

| User | Password | Role |
|------|----------|------|
| admin | admin123 | admin |
| operator | operator123 | operator |
| viewer | viewer123 | viewer |

## Auth model

- `AUTH_ENABLED=true` on incident + remediation (Compose default)
- Bearer JWT for humans; `X-Service-Token` for mesh calls
- Alertmanager **webhooks stay open** (no JWT)
- Health/ready/live/metrics remain public

## API versioning

Legacy paths kept. Versioned aliases:

- `/api/v1/auth/login`
- `/api/v1/incidents`
- `/api/v1/...` remediations

## Ops

```bash
./scripts/backup-postgres.sh
./scripts/restore-postgres.sh backups/sre_incidents_....sql.gz
./scripts/validate-phase7.sh
```

See also: [PHASE7_VALIDATION](PHASE7_VALIDATION.md), [DR](DISASTER_RECOVERY.md),
[SECURITY_REVIEW](SECURITY_REVIEW.md), [runbooks/phase7-auth.md](../runbooks/phase7-auth.md).
