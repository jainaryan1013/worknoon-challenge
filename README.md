# Refund Agent

An AI customer-support agent that processes, denies, or escalates e-commerce refunds. A customer chats with the agent; an admin dashboard replays the agent's full reasoning trace. Containerized monorepo: **FastAPI** backend + agent, **React/Vite** frontend, **PostgreSQL**.

> **Core principle:** the LLM *orchestrates*, deterministic code *authorizes*. Every refund is re-validated by a pure rule engine in the tool layer, so no prompt — however adversarial — can produce a refund the policy forbids.

## Prerequisites

- Docker + Docker Compose
- An API key for OpenAI (default) or Anthropic — or run key-free with the deterministic `fake` provider

## Run

```bash
cp .env.example .env      # then paste your key into .env
docker-compose up --build
```

A fresh clone always rebuilds. The stack comes up in order (db → backend → frontend) via healthchecks. The app boots even without a key; chat returns a clear error until one is provided.

## URLs

- Customer chat: http://localhost:8080/chat
- Admin dashboard: http://localhost:8080/admin
- API docs (OpenAPI): http://localhost:8000/docs

## Documentation

Full documentation lives in [`docs/`](docs/) — start with the [documentation index](docs/README.md).

- [Overview](docs/overview.md) · [Quick start](docs/quickstart.md) · [Architecture](docs/architecture.md)
- [Configuration](docs/configuration.md) · [Data model](docs/data-model.md) · [API reference](docs/api-reference.md)
- [Agent & tools](docs/agent-and-tools.md) · [Rule engine](docs/rule-engine.md) · [Testing](docs/testing.md) · [Known gaps](docs/known-gaps.md)
