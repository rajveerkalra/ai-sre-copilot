# AI Investigation Engine (Phase 4)

Evidence-cited multi-agent RCA using LangGraph + **Model Gateway**, with
ChromaDB runbooks (via Embedding Gateway) and deterministic fallback.

## Architecture

```
Incident → Context Service
                ↓
        Investigation Service  ──▶ Model Gateway ──▶ Ollama / stubs
                │
                └──▶ Knowledge Service ──▶ Embedding Gateway
```

**Hard rule:** Investigation never calls Ollama directly. Every RCA cites
`evidence_id`s. See [docs/AI_INFRASTRUCTURE.md](../../docs/AI_INFRASTRUCTURE.md).

## APIs

| Method | Path | Description |
|--------|------|-------------|
| POST | `/incidents/{id}/investigate` | Run investigation |
| GET | `/investigations/{id}` | Run metadata + report |
| GET | `/investigations/{id}/evidence` | Evidence catalog |
| GET | `/investigations/{id}/rca` | Root cause report |

## Configuration

| Env | Default | Notes |
|-----|---------|-------|
| `MODEL_GATEWAY_URL` | `http://model-gateway:8040` | Sole LLM path |
| `LLM_MODEL` | `llama3.2` | Never hardcoded in agents |
| `LLM_ENABLED` | `true` | Disable → rule fallback |
| `REDIS_URL` | `redis://redis:6379/0` | Context cache |
| `KNOWLEDGE_SERVICE_URL` | `http://knowledge-service:8030` | |

Legacy `OLLAMA_*` env vars are accepted as aliases for `LLM_*`.

## Local tests

```bash
cd services/investigation-service
pip install -r requirements.txt
pytest -q
```
