# Phase 6 Validation

## Automated

```bash
./scripts/validate-phase6.sh
```

## Manual checklist

- [ ] http://localhost:8050 loads Overview
- [ ] KPIs render (open / MTTR / MTTD / queue)
- [ ] Alert trends + AI confidence charts render
- [ ] Incidents list navigates to detail
- [ ] Detail shows timeline; RCA/evidence when available
- [ ] Investigation graph advances with pipeline state
- [ ] Remediation queue lists pending proposals
- [ ] Approve from UI requires operator name; execute only after approve

## Local build

```bash
(cd services/executive-dashboard && npm install && npm run build)
```
