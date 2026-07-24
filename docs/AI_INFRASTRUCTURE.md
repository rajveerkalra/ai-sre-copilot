# AI Infrastructure (pre–Phase 5)

Production hardening of the AI layer. No remediation yet.

## Architecture

```
┌─────────────────────┐     ┌──────────────────┐     ┌────────────┐
│ investigation-svc   │────▶│  model-gateway   │────▶│  Ollama    │
│ (LangGraph agents)  │     │  :8040           │     │  (impl)    │
└─────────┬───────────┘     │  + OpenAI stub   │     └────────────┘
          │                 │  + Anthropic stub│
          │                 └────────┬─────────┘
          │                          │
          │                 ┌────────▼─────────┐
          │                 │     Redis        │
          │                 │     :6379        │
          │                 └────────▲─────────┘
          │                          │
┌─────────▼───────────┐     ┌────────┴─────────┐
│ knowledge-service   │────▶│ embedding-gw     │──── ONNX (default)
│ Chroma (vectors)    │     │ :8041            │──── SentenceTransformers
└─────────────────────┘     │                  │──── OpenAI (stub)
                            └──────────────────┘
```

**Rules**

1. Investigation Service **never** calls Ollama (or any LLM vendor) directly.
2. Knowledge Service **never** loads ONNX / Sentence Transformers locally.
3. Provider selection is **configuration-only** (`LLM_PROVIDER`, `EMBEDDING_PROVIDER`).
4. Every external call uses retry + exponential backoff + timeout + circuit breaker.

## Model Gateway (`:8040`)

| Endpoint | Purpose |
|----------|---------|
| `POST /v1/chat` | Chat completion |
| `POST /v1/generate-json` | JSON-constrained generation |
| `GET /v1/providers` | Active provider + circuit state |

Env: `LLM_PROVIDER=ollama|openai_compatible|anthropic_compatible`, `DEFAULT_MODEL`,
`OLLAMA_BASE_URL`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `REDIS_URL`.

Features: retries, circuit breaker, request logging, token accounting
(`llm_tokens_total`), latency (`llm_latency_seconds`), failures
(`provider_failures_total`).

## Embedding Gateway (`:8041`)

| Endpoint | Purpose |
|----------|---------|
| `POST /v1/embed` | Embed one or more texts |
| `GET /v1/providers` | Active provider |

Env: `EMBEDDING_PROVIDER=onnx|sentence_transformers|openai`.

Embeddings are Redis-cached by content hash. Latency:
`embedding_latency_seconds`.

## Caching (Redis)

| Cache | Owner | Key material |
|-------|-------|--------------|
| Runbook search | knowledge-service | query + top_k |
| Embeddings | embedding-gateway | text hash + model |
| Investigation context | investigation-service | incident_id |

Metric: `cache_hit_ratio{cache=...}`

## Switching providers

```bash
# LLM → OpenAI-compatible (requires key)
LLM_PROVIDER=openai_compatible OPENAI_API_KEY=sk-... docker compose up -d model-gateway

# Embeddings → Sentence Transformers (install optional dep in image)
EMBEDDING_PROVIDER=sentence_transformers docker compose up -d embedding-gateway
```

## Out of scope

Remediation execution, approvals, Phase 5+ features.
