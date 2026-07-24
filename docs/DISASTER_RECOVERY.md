# Disaster Recovery (Phase 7)

## RPO / RTO targets (local Compose)

| Objective | Target | Mechanism |
|-----------|--------|-----------|
| RPO | ≤ 24h (demo) | Nightly `scripts/backup-postgres.sh` |
| RTO | ≤ 30m | Restore dump + `docker compose up -d` |

## Backup

```bash
./scripts/backup-postgres.sh
# → backups/sre_incidents_<UTC>.sql.gz
```

Also back up:

- `runbooks/` and knowledge Chroma volume (`knowledge-chroma`) if customized
- `.env` / secrets (offline, encrypted)

## Restore

```bash
./scripts/restore-postgres.sh backups/sre_incidents_YYYYMMDDTHHMMSSZ.sql.gz
# type RESTORE when prompted
docker compose up -d
./scripts/smoke-test.sh
```

## Failure modes

| Failure | Action |
|---------|--------|
| Single service crash | Compose restart policy; check `/ready` |
| Postgres volume loss | Restore latest dump; re-run Alembic if needed |
| Redis loss | Soft-fail caches; no durable state |
| Ollama / model-gw down | Investigation rule fallback still works |
| Auth secret rotation | Update `JWT_SECRET` everywhere; force re-login |

## Continuity notes

- Remediations never auto-execute — DR does not change the human-approval gate
- Prefer restoring Postgres before restarting investigation/remediation
