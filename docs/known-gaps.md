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

See [`design.md`](design.md) §1 for the full feature/non-goal matrix.
