# Known Gaps & Non-Goals

Documented honestly rather than half-built.

## Non-goals

- **No admin authentication.** Admin routes are read-only and unauthenticated in v1. A real deployment would gate them behind auth; out of scope here.
- **Dispute-email processing is not built.** On a denial the agent hands out a dispute address (`policy_rules.dispute_email`, `disputes@refundagent.example`), and the README documents email disputes as the human-handled path. Actually receiving or processing those emails — no mail handler, inbox, or ticketing integration — is out of scope.
- **Not production-hardened.** No TLS, secrets are `.env`-based, single node, no rate limiting in the shipped stack. This is a local demo.

## In scope (so there's no confusion)

- **Partial and multi-item refunds** — each line item is refundable independently, in whole or partial quantity, on its own delivery date and return window.
- **Projected per-order escalation** — the threshold is evaluated on prior approved refunds on the order plus the current request, before confirmation.
- **Provider abstraction** — OpenAI, Anthropic, and a deterministic `fake` behind one `LLMClient` interface.

## Stretch items (flagged for the reviewer)

- Live metrics widget on the admin dashboard (`GET /api/admin/metrics`).
- Policy versioning (`policy_documents.version` exists; currently version 1).
- Per-session rate limiting / abuse throttle.

## Tooling / tech debt

- **`make lint` is not fully green.** `ruff` and the frontend `tsc --noEmit` pass; **`mypy` reports ≈34 type errors** across the Anthropic LLM client, a few repositories/services, and the tool layer's `verified_customer_id: UUID | None` call sites. The bulk are third-party stub drift (the `anthropic` SDK) and narrow-vs-broad typing gaps. None change runtime behavior, and the deterministic enforcement / adversarial suites are unaffected — but a strict `mypy` gate is not yet satisfied. See [`testing.md`](testing.md#linting).
- **`make lint` runs the backend tools on the host.** Unlike the test targets (Docker-only), the `lint` target calls `ruff`/`mypy` directly, so it needs them installed locally or run via the test image (`docker compose -f docker-compose.test.yml run --rm test sh -c "ruff check . && mypy app"`).
- **The generated frontend client must stay committed.** `apps/frontend/src/api/types.ts` now imports `api/generated/schema.ts`, so that generated file is load-bearing for the frontend build. It is committed for this reason; regenerate via `make gen-client` after any backend schema change.

See [`design.md`](design.md) §1 for the full feature/non-goal matrix.
