# DX shortcuts — see docs/repo-structure.md §6.
.PHONY: up down seed gen-client test test-adv lint
up:         ; docker-compose up --build
down:       ; docker-compose down -v
seed:       ; docker-compose exec backend python -m app.seed.seed
gen-client: ; ./scripts/gen-api-client.sh
test:       ; cd apps/backend && pytest -q && cd ../frontend && npm test
test-adv:   ; cd apps/backend && pytest -q tests/adversarial
lint:       ; cd apps/backend && ruff check . && mypy app ; cd ../frontend && npm run lint
