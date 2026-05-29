# DX shortcuts — see docs/repo-structure.md §6.
.PHONY: up down seed gen-client test test-adv lint
CT = docker compose -f docker-compose.test.yml
up:         ; docker-compose up --build
down:       ; docker-compose down -v
seed:       ; docker-compose exec backend python -m app.seed.seed
gen-client: ; ./scripts/gen-api-client.sh
# Tests run exclusively inside Docker against an ephemeral tmpfs Postgres.
test:       ; $(CT) up --build --abort-on-container-exit --exit-code-from test; code=$$?; $(CT) down -v >/dev/null 2>&1; exit $$code
test-adv:   ; $(CT) run --build --rm test pytest -q tests/adversarial; code=$$?; $(CT) down -v >/dev/null 2>&1; exit $$code
lint:       ; cd apps/backend && ruff check . && mypy app ; cd ../frontend && npm run lint
