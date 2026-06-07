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

## Threat model & resilience

The system's core guarantee is **the LLM orchestrates, deterministic code authorizes**: no prompt — direct, fake-authority, obfuscated, or smuggled through stored data — can produce a refund the rule engine forbids, because every state change re-derives the verdict in code under a row lock. Proven by the adversarial suites (`make test-adv`, `make test-adv-llm`).

Hardened (Scope 1) against the adjacent abuse surface:

- **Conversation capability token.** Acting on a conversation via `POST /api/chat` requires the `Authorization: Bearer <session_token>` minted at creation (`conversations.session_token`). A leaked or guessed `conversation_id` alone — e.g. one read from the unauthenticated admin list — can no longer drive or read a verified conversation. Mismatch is an opaque 404. This is a per-conversation capability, **not** a user-auth system.
- **Second-order / stored prompt injection.** A malicious instruction persisted in CRM data (e.g. a crafted `product_name`) and fed back to the model cannot subvert authorization — covered by `tests/adversarial/test_authz.py`.
- **Input bounds.** `POST /api/chat` caps `selection` at 20 items (`quantity` 1–100) and `message` at 4000 chars, so a crafted body can't drive unbounded work.
- **Per-conversation turn cap.** `MAX_TURNS_PER_CONVERSATION` (default 50) fails closed past the cap — chat returns a clean error without calling the LLM.
- **Fail-closed over-refund guard.** The quantity-invariant re-check writes inside a savepoint, so even if upstream guards were ever weakened, an over-refund row can never survive (`refund_service.process_refund`).

Accepted residual risks for this local demo (see Non-goals / Stretch):

- **Identity is order-number + email, brute-forceable.** Order numbers are sequential; only the email is secret, and there is no attempt throttling. Network-level rate limiting remains a stretch item.
- **System-prompt extraction is possible** via a determined injection. Low impact: the prompt holds no secrets, no keys, and no other customer's data, and grants no authority — enforcement is in code.
- **No network-level rate limiting** and **no admin auth** (below).

## Stretch items (flagged for the reviewer)

- Live metrics widget on the admin dashboard (`GET /api/admin/metrics`).
- Policy versioning (`policy_documents.version` exists; currently version 1).
- Network/IP rate limiting / abuse throttle (the per-conversation turn cap is a partial backstop, not a full rate limiter).

## Tooling / tech debt

- **`make lint` is not fully green.** `ruff` and the frontend `tsc --noEmit` pass; **`mypy` reports ≈34 type errors** across the Anthropic LLM client, a few repositories/services, and the tool layer's `verified_customer_id: UUID | None` call sites. The bulk are third-party stub drift (the `anthropic` SDK) and narrow-vs-broad typing gaps. None change runtime behavior, and the deterministic enforcement / adversarial suites are unaffected — but a strict `mypy` gate is not yet satisfied. See [`testing.md`](testing.md#linting).
- **`make lint` runs the backend tools on the host.** Unlike the test targets (Docker-only), the `lint` target calls `ruff`/`mypy` directly, so it needs them installed locally or run via the test image (`docker compose -f docker-compose.test.yml run --rm test sh -c "ruff check . && mypy app"`).
- **The generated frontend client must stay committed.** `apps/frontend/src/api/types.ts` now imports `api/generated/schema.ts`, so that generated file is load-bearing for the frontend build. It is committed for this reason; regenerate via `make gen-client` after any backend schema change.

See [`design.md`](design.md) §1 for the full feature/non-goal matrix.
