# Refund Agent

An AI customer-support agent that processes, denies, or escalates e-commerce refunds. A customer chats with the agent; an admin dashboard shows the agent's full reasoning trace. Built as a containerized monorepo: **FastAPI** backend + agent, **React/Vite** frontend, **PostgreSQL**.

> **Core principle:** the LLM *orchestrates*, deterministic code *authorizes*. Every refund is re-validated by a pure rule engine in the tool layer, so no prompt — however adversarial — can produce a refund the policy forbids.

## Prerequisites

- Docker + Docker Compose
- An API key for OpenAI (default) or Anthropic

## Run

```bash
cp .env.example .env      # then paste your key into .env
docker-compose up --build
```

A fresh clone always rebuilds. The stack comes up in order (db → backend → frontend) via healthchecks.

## URLs

- Customer chat: http://localhost:8080/chat
- Admin dashboard: http://localhost:8080/admin
- API docs (OpenAPI): http://localhost:8000/docs

The app boots even without an API key; chat returns a clear error until one is provided.

## Architecture

A bounded tool-calling loop. The agent calls tools to verify identity, look up orders/policy, present return options, and request refunds. The tool layer enforces policy deterministically (the rule engine), so authorization never depends on the model's output. Full design in [`docs/`](docs/):

- [`docs/design.md`](docs/design.md) — system architecture
- [`docs/repo-structure.md`](docs/repo-structure.md) — monorepo layout
- [`docs/components/`](docs/components/) — per-component specs (database, rule engine, tools, agent loop, API, frontend, infra, adversarial suite)

## Agent resilience

The system is hardened against prompt injection by enforcing every decision in code, not in the prompt (identity from server-side context, amounts computed not model-supplied, ownership re-checked, projected per-order $500 cap, quantity invariant under row lock). The adversarial test suite proves it:

```bash
make test-adv        # deterministic enforcement + invariants (no key needed)
```

See [`docs/components/08-adversarial-eval-suite.md`](docs/components/08-adversarial-eval-suite.md).

## Configuration

All variables are documented in [`.env.example`](.env.example) and `docs/components/07-infra.md §6`.

## Known gaps / non-goals

- **No admin authentication** — out of scope; admin routes are read-only.
- **Dispute-email processing** — on a denial the agent hands out a dispute address, but receiving/processing those emails is not built.
- **Not production-hardened** — no TLS, `.env`-based secrets, single node. This is a local demo.
