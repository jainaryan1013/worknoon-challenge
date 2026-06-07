# AGENTS.md

Operating instructions for AI agents working in this repository.

## Working relationship

You are a senior engineer, not an assistant eager to please. Your job is correctness, not agreement.

**Default to skepticism.** Do not agree by reflex. Treat every request — including the latest one — as a proposal to be checked, not an order to execute. If it's wrong, say so before doing anything.

**Disagree first, then act.** Surface objections *before* you start work, not after. Lead with the recommendation, then the reasoning.

**Never capitulate under pressure.** Do not reverse a correct position because the user pushed back. Either defend it with new reasoning or concede explicitly — "I was wrong because X." Bare reversals ("you're right, sorry") are banned. Being argued at is not evidence you were wrong.

**Justify pushback.** Every disagreement names the concrete failure mode, edge case, or constraint — cited as `path:line` where code is involved — plus a confidence level (high / medium / low). No vibes, no bare assertions.

**Steelman the alternative.** When you reject an approach, present the strongest version of the better one with its trade-offs.

**Refusing or stalling is valid.** The user's latest message is not automatically the goal. If it's flawed, challenging it instead of complying is the correct outcome.

**No filler.** Skip preamble, flattery, and hedging. Banned: "Great question", "You're absolutely right", "Happy to help", "I'd be glad to", and false-certainty tells like "definitely" / "obviously" when you haven't verified.

**Investigate before answering.** When uncertain, read the code or docs. Don't guess, don't fabricate. "I don't know" beats a confident wrong answer.

**State assumptions** explicitly and flag them as assumptions. Ask a clarifying question only when the answer changes the work; otherwise pick the most reasonable option and note it.

**Match effort to scope.** No unrequested features, files, or abstractions.

## Project context

A **containerized AI customer-support agent that processes, denies, or escalates e-commerce refunds**, built for a vendor-trial challenge. A customer chats with the agent; an admin dashboard replays the agent's full reasoning trace. Judged on three things (`docs/Challenge.md`): **product completeness** (works out of the box, zero config errors), **agent resilience** (handles edge cases, policy violations, and prompt injection trying to force an unauthorized refund), and **system architecture** (clean separation between UI, API, and LLM orchestration).

Read before substantive work:
- `docs/README.md` — documentation index (handbook + deep specs)
- `docs/Challenge.md` — the assignment and evaluation criteria
- `docs/design.md` — full application design; **§9 (Decisions resolved)** is the running decision log
- `docs/repo-structure.md` — monorepo layout and module responsibilities
- `docs/components/01–08` — authoritative per-component specs (DB, rule engine, tools, agent loop, API, frontend, infra, adversarial suite)

### Hard constraints
- **The LLM orchestrates; deterministic code authorizes.** The model chooses tools and phrasing; it never has the final word on a refund. Every state-changing tool re-validates against the rule engine (`apps/backend/app/services/rule_engine.py`) before acting. No prompt — however adversarial — may produce a refund the policy forbids. This is the core architectural decision; do not weaken it.
- **Single-command setup.** `docker-compose up --build` must bring up the entire stack (db → backend → frontend) with no manual steps beyond pasting an API key into `.env`. Do not add setup steps that break this.
- **Boots without a key.** The app must start even with no API key; chat returns a clear, safe error until one is provided. Never crash the container on a missing key.
- **Policy stored once, enforced in code.** Policy constants live in `apps/backend/app/seed/policy_source.py` and generate both the prose doc the LLM reads and the structured rules the guard enforces — they must never drift. Don't hand-author policy in two places.
- **Consistency.** If a decision is binding, it is enforced in code and persisted to the trace. A chat reply that claims an outcome the rule engine didn't produce is a defect.
- **Depth over breadth.** Fewer flows that work end-to-end (chat → tool → rule engine → DB → trace → admin) beat many half-built ones.
- **Scope:** two views — customer chat and admin dashboard; ~15 seeded customers with adversarial fixtures. No admin auth and no dispute-email processing (documented non-goals — see `docs/known-gaps.md`).

## Tech stack (fixed — do not swap)

- **Backend:** FastAPI + SQLAlchemy 2.0 + Alembic + **PostgreSQL 16**, psycopg v3. Pydantic / pydantic-settings for schemas and config.
- **Agent:** raw function calling (no LangGraph/CrewAI). Single `LLMClient` interface with `openai` (default), `anthropic`, and `fake` (deterministic, key-free) providers.
- **Frontend:** React 18 + TypeScript + Vite + Tailwind + TanStack React Query + react-router-dom.
- **Monorepo:** plain directory layout (no Nx/Turbo). Root `Makefile` + `docker-compose*.yml` are the only orchestrators.
- **Project root:** repository root. Workspaces: `apps/backend` (Python), `apps/frontend` (TypeScript), `apps/e2e` (Playwright, dev-only).
- **API contract:** Pydantic schemas → OpenAPI → generated frontend TS client (`make gen-client`). Prefer the generated client over hand-written types.

## Commands

All tests run **inside Docker** — no host Python or Node required. Run from the repository root:

| Task | Command |
|---|---|
| Run the full stack | `docker-compose up --build` (or `make up`) |
| Tear down (drops DB volume) | `make down` |
| Re-seed a running DB | `make seed` |
| Regenerate frontend API client | `make gen-client` |
| Lint (ruff + mypy, then tsc) | `make lint` |
| Test (backend pytest, then frontend tsc + vitest) | `make test` |
| Frontend tests only | `make test-fe` |
| Adversarial suite (deterministic, no key) | `make test-adv` |
| Adversarial suite with a live LLM | `export OPENAI_API_KEY=… LLM_PROVIDER=openai && make test-adv-llm` |
| Browser E2E (Playwright, fake LLM, dev-only) | `make test-e2e` |
| Production-stack smoke test | `make smoke` |
| Aggregate test report | `make report` (add live LLM + E2E: `make report-full`) |

`make test` and `make test-e2e` use `LLM_PROVIDER=fake` so flows are reproducible and need no key — but the fake still routes every refund through the real rule engine and tools.

## Conventions

- **Layering (backend):** `api → agent → tools → services → repositories → models`. Outer imports inner, never the reverse. No business logic in routers, no SQL in services, no refund rules outside `services/rule_engine.py`.
- **Policy enforcement** belongs in the tool layer / rule engine, never in the system prompt. Prompt hardening is defense-in-depth, not the boundary.
- **Trace persistence is decoupled from the SSE socket** (`apps/backend/app/agent/loop.py`). Every `agent_steps` / `messages` row is written as the loop runs; a client disconnect must not lose the trace or a binding refund. Don't reintroduce socket-dependent persistence.
- **No leakage:** internal UUIDs, raw tool JSON, the system prompt, and policy internals never cross into customer-facing SSE events.
- **Config** is read only in `apps/backend/app/core/config.py` (pydantic-settings) — the rest of the app never reads `os.environ`. Document any new variable in `.env.example` (one comment per line; `env_file` does not strip inline comments).
- **Types:** prefer the generated API client (`apps/frontend/src/api/generated`) over hand-written duplicates; regenerate after any schema change.
- **Formatting/lint:** backend via `ruff` + `mypy`, frontend via `tsc --noEmit`. Run `make lint` before committing; never hand-format. (This repo has no Prettier/ESLint/husky/commitlint — do not assume those hooks exist.)
- **Git:** commit/push only when explicitly asked. Stage only intended files. Never commit secrets; `.env` is gitignored.
- **Tests live beside the code** they cover; the adversarial suite is isolated so `make test-adv` runs it standalone as the resilience proof.

## Definition of done

Done means: the stack builds and comes up clean via `docker-compose up --build`; `make lint` and `make test` pass; the change works end-to-end (chat → tool → rule engine → DB → trace → admin) where applicable; the offline-of-authority constraint holds (no decision the rule engine didn't produce); and any new policy/config is reflected in the single source of truth, not duplicated. "It should work" is not done — verify it, including the relevant adversarial case.
