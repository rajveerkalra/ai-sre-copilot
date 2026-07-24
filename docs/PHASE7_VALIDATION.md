# Phase 7 Validation

```bash
./scripts/validate-phase7.sh
```

## Checklist

- [ ] `POST /auth/login` returns JWT
- [ ] `GET /auth/me` requires Bearer
- [ ] Remediation/incident return **401** without token
- [ ] Operator can list remediations; viewer can read
- [ ] `/api/v1/...` paths work
- [ ] Jaeger UI at http://localhost:16686
- [ ] Dashboard login at http://localhost:8050/login
- [ ] `./scripts/backup-postgres.sh` produces a gzip dump

## Unit tests

```bash
(cd services/auth-service && PYTHONPATH=../..:../../libs pytest -q)
(cd services/remediation-service && PYTHONPATH=../..:../../libs pytest -q)
```
