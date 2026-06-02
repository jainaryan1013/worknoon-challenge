# DX shortcuts — see docs/repo-structure.md §6.
.PHONY: up down seed gen-client test test-fe test-adv test-adv-llm test-e2e smoke report report-full lint
CE = docker compose -f docker-compose.e2e.yml
CT = docker compose -f docker-compose.test.yml
up:         ; docker-compose up --build
down:       ; docker-compose down -v
seed:       ; docker-compose exec backend python -m app.seed.seed
gen-client: ; ./scripts/gen-api-client.sh
# Tests run exclusively inside Docker. Backend (pytest + ephemeral Postgres),
# then frontend (tsc + vitest). Fails if either suite fails.
test:       ; $(CT) up --build --abort-on-container-exit --exit-code-from test; code=$$?; if [ $$code -eq 0 ]; then $(CT) --profile fe run --build --rm frontend-test; code=$$?; fi; $(CT) --profile fe down -v >/dev/null 2>&1; exit $$code
test-fe:    ; $(CT) --profile fe run --build --rm frontend-test; code=$$?; $(CT) --profile fe down -v >/dev/null 2>&1; exit $$code
test-adv:   ; $(CT) run --build --rm test pytest -q tests/adversarial; code=$$?; $(CT) down -v >/dev/null 2>&1; exit $$code
# LLM-in-the-loop injection corpus — needs a real key; pass it from your shell:
#   export OPENAI_API_KEY=sk-...  LLM_PROVIDER=openai  && make test-adv-llm
test-adv-llm: ; $(CT) run --build --rm -e LLM_PROVIDER -e LLM_MODEL -e OPENAI_API_KEY -e ANTHROPIC_API_KEY test pytest -q -m llm tests/adversarial; code=$$?; $(CT) down -v >/dev/null 2>&1; exit $$code
# Dev-only browser E2E (deterministic fake LLM). Never part of the shipped stack.
test-e2e:   ; $(CE) up --build --abort-on-container-exit --exit-code-from e2e; code=$$?; $(CE) down -v >/dev/null 2>&1; exit $$code
# Compose smoke test of the production stack (health 200).
smoke:      ; chmod +x scripts/smoke.sh && ./scripts/smoke.sh
# Run every suite and aggregate JUnit output into reports/test-report.md.
report:     ; \
	mkdir -p reports; \
	$(CT) run --build --rm -v $(CURDIR)/reports:/reports test pytest -q --junitxml=/reports/backend.xml tests || true; \
	$(CT) --profile fe run --build --rm -v $(CURDIR)/reports:/reports frontend-test sh -c "npx vitest run --reporter=junit --outputFile=/reports/frontend.xml" || true; \
	$(CT) run --rm --no-deps -v $(CURDIR)/reports:/reports test python scripts/aggregate_report.py /reports/backend.xml /reports/frontend.xml; \
	code=$$?; $(CT) --profile fe down -v >/dev/null 2>&1; echo "Report written to reports/test-report.md"; exit $$code
# Full report: also runs the LIVE LLM injection corpus (needs keys exported, like
# test-adv-llm) and the Playwright E2E. Backend excludes llm here so the live
# results aren't double-counted.
report-full: ; \
	mkdir -p reports; \
	$(CT) run --build --rm -v $(CURDIR)/reports:/reports test pytest -q -m "not llm" --junitxml=/reports/backend.xml tests || true; \
	$(CT) --profile fe run --build --rm -v $(CURDIR)/reports:/reports frontend-test sh -c "npx vitest run --reporter=junit --outputFile=/reports/frontend.xml" || true; \
	$(CT) run --rm -e LLM_PROVIDER -e LLM_MODEL -e OPENAI_API_KEY -e ANTHROPIC_API_KEY -v $(CURDIR)/reports:/reports test pytest -q -m llm --junitxml=/reports/llm.xml tests/adversarial || true; \
	$(CE) up --build --abort-on-container-exit --exit-code-from e2e || true; \
	cp apps/e2e/artifacts/junit.xml reports/e2e.xml 2>/dev/null || true; \
	$(CT) run --rm --no-deps -v $(CURDIR)/reports:/reports test python scripts/aggregate_report.py /reports/backend.xml /reports/frontend.xml /reports/llm.xml /reports/e2e.xml; \
	code=$$?; $(CT) --profile fe down -v >/dev/null 2>&1; $(CE) down -v >/dev/null 2>&1; echo "Report: reports/test-report.md"; exit $$code
lint:       ; cd apps/backend && ruff check . && mypy app ; cd ../frontend && npm run lint
