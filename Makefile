.PHONY: up down smoke test-sample-app test-incident-service test-context-service test-investigation-service eval-investigation simulate logs ps

up:
	./scripts/up.sh

down:
	./scripts/down.sh

smoke:
	./scripts/smoke-test.sh

test-sample-app:
	cd services/sample-app && \
	  PYTHONPATH=../..:. python3 -m pytest -q

test-incident-service:
	cd services/incident-service && \
	  python3 -m pytest -q

test-context-service:
	cd services/context-service && \
	  python3 -m pytest -q

test-investigation-service:
	cd services/investigation-service && \
	  PYTHONPATH=../..:. python3 -m pytest -q

eval-investigation:
	cd services/investigation-service && \
	  PYTHONPATH=../..:. python3 -m eval.run_eval --json-out eval-report.json

simulate:
	./scripts/simulate-incident.sh $(or $(SCENARIO),error_storm) $(or $(DURATION),120)

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps
