# Remediation Service (Phase 5)

Human-in-the-loop remediation proposals. **No automatic execution.**

## Flow

```
RCA → propose → pending queue → approve/reject → execute (only if approved)
```

## APIs

| Method | Path | Description |
|--------|------|-------------|
| POST | `/incidents/{id}/remediations/propose` | Map RCA → proposals |
| GET | `/incidents/{id}/remediations` | List for incident |
| GET | `/remediations/pending` | Approval queue |
| GET | `/remediations/{id}` | Proposal detail |
| POST | `/remediations/{id}/approve` | `{approved_by, comment}` |
| POST | `/remediations/{id}/reject` | `{rejected_by, comment}` |
| POST | `/remediations/{id}/execute` | Only when `status=approved` |

## Safety

| Env | Default | Effect |
|-----|---------|--------|
| `EXECUTION_ENABLED` | `true` | Master kill switch |
| `ALLOW_MUTATIONS` | `false` | Forces dry-run for rollback/scale |
| `ALLOW_COMPOSE_RESTART` | `false` | Blocks live Compose restart |

`clear_fault` against sample-app is the safe demo path (low risk, not dry-run by default).

## Tests

```bash
cd services/remediation-service
pip install -r requirements.txt
pytest -q
```
