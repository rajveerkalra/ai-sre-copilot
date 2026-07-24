# Phase 4 Validation Checklist

## Prerequisites

- [ ] `docker compose up -d --build` healthy (Phases 1–4)
- [ ] Postgres reachable
- [ ] Context service ready
- [ ] Knowledge service ready (may take 1–2 min on first boot for embeddings)
- [ ] Investigation service ready
- [ ] (Optional) `docker compose exec ollama ollama pull $OLLAMA_MODEL`

## Automated

```bash
./scripts/validate-phase4.sh
```

## Manual checks

### Knowledge

```bash
curl -sf http://localhost:8030/ready | jq
curl -sf http://localhost:8030/documents | jq '.count'
curl -sf -X POST http://localhost:8030/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"OOMKilled memory","top_k":3}' | jq
```

Expect: `count >= 8`, search returns `evidence_id` fields.

### Investigation (fallback OK without model)

```bash
# Create or pick an open incident
ID=$(curl -sf 'http://localhost:8000/incidents?status=open&page_size=1' | jq -r '.items[0].id')
curl -sf -X POST "http://localhost:8020/incidents/$ID/collect" | jq '.status'
INV=$(curl -sf -X POST "http://localhost:8031/incidents/$ID/investigate" | jq)
echo "$INV" | jq
INV_ID=$(echo "$INV" | jq -r '.investigation_id')
curl -sf "http://localhost:8031/investigations/$INV_ID/rca" | jq
curl -sf "http://localhost:8031/investigations/$INV_ID/evidence" | jq '.count'
```

Expect:

- [ ] `root_cause` present
- [ ] `evidence_ids` non-empty **or** root_cause is `Insufficient evidence`
- [ ] No invented IDs outside evidence catalog
- [ ] `confidence` in 0–100
- [ ] Prometheus scrapes `investigation-service` / `knowledge-service`

### Metrics

```bash
curl -sf http://localhost:8031/metrics | grep -E 'investigation_duration|llm_|fallback_total|agent_duration'
curl -sf http://localhost:8030/metrics | head
```

### Unit tests

```bash
(cd services/investigation-service && pytest -q)
(cd services/knowledge-service && pytest -q)
```

## Pass criteria

| Check | Pass |
|-------|------|
| Services healthy | yes |
| Seeded runbooks searchable | yes |
| Investigate returns structured RCA | yes |
| Citations validated | yes |
| Fallback works without Ollama model | yes |
| No remediation / approvals shipped | yes (Phase 5) |
