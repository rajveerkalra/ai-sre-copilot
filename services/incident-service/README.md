# Incident Service — Phase 2

Production-style incident engine: Alertmanager webhook ingestion, fingerprint
deduplication, PostgreSQL persistence, chronological timelines, and REST APIs.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/webhooks/alertmanager` | Ingest Alertmanager webhook |
| GET | `/incidents` | List incidents (`status`, `severity`, `page`, `page_size`) |
| GET | `/incidents/{id}` | Incident detail + timeline |
| GET | `/incidents/{id}/timeline` | Timeline only |
| POST | `/incidents/{id}/resolve` | Resolve incident |
| POST | `/incidents/{id}/notes` | Add operator note |
| GET | `/health` `/live` `/ready` | Probes |
| GET | `/metrics` | Prometheus metrics |

## Deduplication

Fingerprint = SHA-256 of:

`alertname | namespace | pod | service | instance`

Repeating alerts against an **open** incident increment `occurrence_count` and
append `alert_repeated` timeline events. Resolved incidents can be re-opened as
a **new** incident if the same fingerprint fires again.

## Local tests

```bash
cd services/incident-service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## Compose

Incident service listens on port **8000** and depends on Postgres.
Alembic migrations run automatically on startup.
