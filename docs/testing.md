# Testing

All tests run inside Docker — no host Python or Node needed. The backend test stack uses an ephemeral Postgres on tmpfs (wiped every run). `make test` and `make test-e2e` run with the deterministic **fake LLM** (`LLM_PROVIDER=fake`), so flows are reproducible and need no API key. The fake still routes every refund through the real rule engine and tools, so authorization is exercised exactly as in production.

## Make targets

| Target | What it runs | Needs a key? |
|---|---|---|
| `make test` | Backend (pytest + ephemeral Postgres), then frontend (tsc + vitest). Fails if either fails. | No |
| `make test-fe` | Frontend only (lint + vitest). | No |
| `make test-adv` | Adversarial suite only — deterministic enforcement + invariants. The F9 resilience proof. | No |
| `make test-adv-llm` | LLM-in-the-loop injection corpus (pytest `-m llm`). Export a real key first. | **Yes** |
| `make test-e2e` | Browser end-to-end (Playwright) against the full stack with the fake LLM. Dev-only. | No |
| `make smoke` | Brings the production stack up and asserts `/api/health` is 200. | No |
| `make report` | Runs every suite and aggregates JUnit output into `reports/test-report.md`. | No |
| `make report-full` | `report` plus the live LLM injection corpus and Playwright E2E. | **Yes** |

The `llm` marker (declared in `pyproject.toml`) gates tests that call a real provider — they are opt-in. To run them:

```bash
export OPENAI_API_KEY=sk-...  LLM_PROVIDER=openai
make test-adv-llm
```

## Test layout (`apps/backend/tests/`)

- `unit/` — pure-function tests: rule-engine branches, seed fixtures, model DDL, migration consistency, OpenAI param shaping.
- `integration/` — against a test DB: agent loop, API, tools, policy service, DB constraints, concurrency, fake LLM.
- `adversarial/` — the resilience proof: `test_enforcement.py`, `test_invariants.py`, `test_injection.py`, plus an `attacks.yaml` corpus.

Frontend tests (Vitest + Testing Library) live beside their features under `apps/frontend/src`.

## Adversarial / resilience suite

The suite proves that no prompt — however adversarial — can produce a refund the policy forbids, because every decision is enforced in code, not in the prompt: identity comes from server-side context, amounts are computed not model-supplied, ownership is re-checked, the projected per-order cap is enforced, and the quantity invariant holds under a row lock. `make test-adv` runs the deterministic portion with no API key; `make test-adv-llm` adds a live-model injection corpus.

Authoritative spec: `docs/components/08-adversarial-eval-suite.md`.

## E2E artifacts

The Playwright suite writes milestone screenshots and traces to `apps/e2e/artifacts/` for manual review. Playwright is a dev dependency and is **never** part of the shipped `docker-compose.yml` image — the E2E stack is `docker-compose.e2e.yml`.

## Validating real behavior

Run the agent end-to-end with a genuine key (`LLM_PROVIDER=openai` or `anthropic`) via `docker-compose up` to validate live behavior, in addition to the deterministic suites above.
