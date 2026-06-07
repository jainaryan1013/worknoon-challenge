# Quick Start

## Prerequisites

- Docker and Docker Compose.
- An API key for OpenAI (default) or Anthropic. The app also boots with no key using the deterministic `fake` provider — useful for a key-free demo, but the `fake` provider is test/demo scaffolding only.

## Run

```bash
cp .env.example .env      # then paste your API key into .env
docker-compose up --build
```

A fresh clone always rebuilds. The stack comes up in dependency order — `db` → `backend` → `frontend` — gated by healthchecks. The backend runs migrations and conditional seeding (`SEED_ENABLED`, idempotent) in its container entrypoint before uvicorn starts.

The app boots even without an API key; chat returns a clear, safe error until a key is provided. It never crashes the container on a missing key.

## URLs

| Surface | URL |
|---|---|
| Customer chat | http://localhost:8080/chat |
| Admin dashboard | http://localhost:8080/admin |
| API docs (OpenAPI / Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/api/health |

The frontend (nginx serving the built SPA) listens on host port **8080**; the backend (uvicorn) on **8000**. Postgres is not published to the host by default — uncomment the `ports` line under `db` in `docker-compose.yml` for local DB inspection.

## Configure the LLM provider

Set `LLM_PROVIDER` in `.env` to `openai` (default), `anthropic`, or `fake`, and supply the matching key. See [`configuration.md`](configuration.md) for the full variable list.

## Common commands

```bash
make up            # docker-compose up --build
make down          # docker-compose down -v  (also drops the DB volume)
make seed          # re-run seeding against a running DB
make gen-client    # regenerate the frontend TS client from backend OpenAPI
make lint          # ruff + mypy (backend), tsc (frontend)
```

See [`testing.md`](testing.md) for every test target and [`configuration.md`](configuration.md) for environment variables.
