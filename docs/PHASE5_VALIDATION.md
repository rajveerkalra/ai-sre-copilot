# Phase 5 Validation

## Automated

```bash
./scripts/validate-phase5.sh
```

## Manual checklist

- [ ] `GET http://localhost:8032/ready` healthy
- [ ] Propose returns ≥1 proposal for investigated incident
- [ ] Execute without approve → **409**
- [ ] Approve → execute `clear_fault` succeeds against sample-app
- [ ] Incident timeline includes `remediation_proposed` / `approved` / `executed`
- [ ] `GET /remediations/pending` empties after approve
- [ ] Prometheus scrapes `remediation-service`

## Unit tests

```bash
(cd services/remediation-service && pytest -q)
```
