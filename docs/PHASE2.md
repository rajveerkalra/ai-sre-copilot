# Phase 2 — Incident Engine

## Scope

Replace the Phase 1 webhook sink with a durable Incident Service backed by PostgreSQL.

| Component | Role | Port |
|-----------|------|------|
| postgres | Incident / timeline / payload store | 5432 |
| incident-service | Webhook ingest, dedup, REST APIs | 8000 |

Alertmanager now posts to `http://incident-service:8000/webhooks/alertmanager`.

## Data model

- `incidents` — open/resolved incidents with fingerprint + occurrence_count
- `timeline_events` — chronological audit of incident lifecycle
- `alert_payloads` — raw Alertmanager JSON for forensics

Partial unique index: at most one **open** incident per fingerprint.

## Bring-up

```bash
cp .env.example .env   # if needed
./scripts/up.sh
./scripts/smoke-test.sh
```

## Manual verification

See [PHASE2_VALIDATION.md](./PHASE2_VALIDATION.md).

## Out of scope

Context collectors, AI investigation, remediation, React UI (Phases 3–6).
