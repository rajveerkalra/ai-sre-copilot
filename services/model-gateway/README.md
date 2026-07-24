# Model Gateway

Provider-abstracted LLM access for the AI SRE Copilot.

- Providers: `ollama` (implemented), `openai_compatible` (stub), `anthropic_compatible` (stub)
- Resilience: retry, exponential backoff, timeout, circuit breaker
- Observability: `llm_latency_seconds`, `provider_failures_total`, token counters, request logs
- Optional Redis response cache

```bash
curl -s http://localhost:8040/v1/providers | jq
curl -s -X POST http://localhost:8040/v1/generate-json \
  -H 'Content-Type: application/json' \
  -d '{"system":"Return JSON","prompt":"{\"ok\":true}","agent":"demo"}' | jq
```

Switch provider: `LLM_PROVIDER=openai_compatible` + `OPENAI_API_KEY`.
