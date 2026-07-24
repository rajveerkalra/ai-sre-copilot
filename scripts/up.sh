#!/usr/bin/env bash
# Bring up Phase 1 observability stack
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "No .env found — copying .env.example"
  cp .env.example .env
fi

echo "==> Building and starting Phase 1–4 stack..."
docker compose up -d --build

echo "==> Waiting for health..."
services=(sample-app postgres prometheus loki context-service incident-service alertmanager grafana redis embedding-gateway model-gateway knowledge-service investigation-service remediation-service auth-service executive-dashboard)
for s in "${services[@]}"; do
  echo -n "  waiting for $s ... "
  case "$s" in
    sample-app) cname=ai-sre-sample-app ;;
    incident-service) cname=ai-sre-incident-service ;;
    context-service) cname=ai-sre-context-service ;;
    knowledge-service) cname=ai-sre-knowledge-service ;;
    investigation-service) cname=ai-sre-investigation-service ;;
    remediation-service) cname=ai-sre-remediation-service ;;
    executive-dashboard) cname=ai-sre-executive-dashboard ;;
    auth-service) cname=ai-sre-auth-service ;;
    model-gateway) cname=ai-sre-model-gateway ;;
    embedding-gateway) cname=ai-sre-embedding-gateway ;;
    *) cname="ai-sre-${s}" ;;
  esac
  # Knowledge / embedding may need longer first boot
  max=90
  if [[ "$s" == "knowledge-service" || "$s" == "embedding-gateway" ]]; then
    max=180
  fi
  for i in $(seq 1 "$max"); do
    health="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cname" 2>/dev/null || echo "missing")"
    if [[ "$health" == "healthy" || "$health" == "running" ]]; then
      echo "$health"
      break
    fi
    if [[ $i -eq $max ]]; then
      echo "TIMEOUT ($health)"
      docker compose ps
      docker compose logs --tail=80 "$s" || true
      exit 1
    fi
    sleep 2
  done
done

echo
echo "Phase 1–7 is up."
echo "  Executive Dashboard:     http://localhost:8050  (operator/operator123)"
echo "  Auth Service:            http://localhost:8060/docs"
echo "  Jaeger:                  http://localhost:16686"
echo "  Sample App:              http://localhost:8080/docs"
echo "  Incident Service:        http://localhost:8000/docs"
echo "  Context Service:         http://localhost:8020/docs"
echo "  Knowledge Service:       http://localhost:8030/docs"
echo "  Investigation Service:   http://localhost:8031/docs"
echo "  Remediation Service:     http://localhost:8032/docs"
echo "  Model Gateway:           http://localhost:8040/docs"
echo "  Embedding Gateway:       http://localhost:8041/docs"
echo "  Prometheus:              http://localhost:9090"
echo "  Alertmanager:            http://localhost:9093"
echo "  Grafana:                 http://localhost:3000  (admin/admin)"
echo "  Loki:                    http://localhost:3100/ready"
echo "  Ollama:                  http://localhost:11434"
echo
echo "Validate Phase 9 (portfolio):"
echo "  ./scripts/validate-phase9.sh"
echo "Live demo:"
echo "  ./scripts/demo.sh"
echo "Validate Phase 8 (K8s packaging):"
echo "  ./scripts/validate-phase8.sh"
echo "Validate Phase 7:"
echo "  ./scripts/validate-phase7.sh"
echo "Validate Phase 6:"
echo "  ./scripts/validate-phase6.sh"
echo "Validate Phase 4:"
echo "  ./scripts/validate-phase4.sh"
echo "Optional — pull LLM model (fallback works without it):"
echo "  docker compose exec ollama ollama pull \${OLLAMA_MODEL:-llama3.2}"
echo "Simulate an incident:"
echo "  ./scripts/simulate-incident.sh error_storm"
