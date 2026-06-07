# Data Model

PostgreSQL. Four logical groups. Authoritative schema lives in `docs/components/01-database.md`; this is the working summary.

## Tables

**CRM / commerce** (seeded, read-mostly)

- `customers` — `id`, `name`, `email` (unique), `loyalty_tier` (`standard | gold | vip`), `created_at`.
- `orders` — `id`, `customer_id`, `order_number` (unique, e.g. `ORD-1042`), `status` (`placed | shipped | partially_delivered | delivered | cancelled` — fulfillment only, **no refund state**), `total_amount`, `currency`, `ordered_at`. Refund state is **derived** from item refunds, not stored.
- `order_items` — `id`, `order_id`, `product_name`, `sku`, `category`, `quantity`, `unit_price`, `is_final_sale`, `return_window_days` (default 30), `delivered_at` (per-item; NULL until delivered).

**Refund state** (written by the agent)

- `refunds` — per line item, partial quantity. `id`, `order_id` (denormalized for per-order aggregation), `order_item_id`, `customer_id`, `quantity`, `amount` (`unit_price * quantity`), `status` (`approved | denied | escalated`), `reason_code`, `reason`, `policy_refs` (JSONB), `decided_by` (`agent | human`), `conversation_id`, `created_at`. There is deliberately **no** `UNIQUE` constraint on the item — integrity is the quantity invariant under a row lock.

**Conversation + observability** (written by the agent)

- `conversations` — `id`, `customer_id` (NULL until identity verified), `status` (`active | resolved | escalated`), `created_at`.
- `messages` — `id`, `conversation_id`, `role` (`system | user | assistant | tool`), `content`, `created_at`.
- `agent_steps` — the reasoning trace. `id`, `conversation_id`, `message_id` (NULL), `step_no`, `type` (`model_text | tool_call | tool_result | decision`), `tool_name`, `tool_input` (JSONB), `tool_output` (JSONB), `latency_ms`, `created_at`.

**Policy** (seeded)

- `policy_documents` — `id`, `version`, `body_markdown`, `created_at`. The prose the LLM reads and cites.
- `policy_rules` — `id`, `key` (unique), `value` (JSONB), `description`. The structured thresholds/flags the guard enforces.

## Policy stored twice, on purpose

The full text doc (`policy_documents`) is what the LLM reads for reasoning and citation; the structured `policy_rules` is what deterministic code enforces. Both are generated from the **same constants** in `app/seed/policy_source.py`, so the text the model cites and the values the code enforces can never drift. See [`rule-engine.md`](rule-engine.md) for the constants.

## Constraints that do real work

- **Quantity invariant** — `SUM(approved refund units) ≤ order_items.quantity`, enforced under a `SELECT … FOR UPDATE` row lock. Prevents over-refunds even under retries, races, or a confused model. The row lock spans the whole chat turn (the chat router commits only after the turn finishes).
- **Identity gate** — `conversations.customer_id` must be set (via `verify_identity`) before any order action; order tools filter by it.
- **Per-item eligibility** — `delivered_at` and `return_window_days` are per item, so a single order can mix refundable and non-refundable lines.

## Seed data

Seeding runs at backend startup (gated by `SEED_ENABLED`, idempotent — skips if data exists) and generates ~15 customers (8 named fixtures + 7 fillers) with deliberately adversarial per-item cases so every edge case is demonstrable:

- a final-sale item alongside a refundable sibling (item-level deny, sibling approves),
- an item past its return window (deny),
- an undelivered item (NEEDS_INFO),
- a mixed-delivery order (one item refundable, one not yet delivered),
- a partially-then-fully refunded line (partial-quantity invariant),
- a selection projecting past the threshold on an order (escalate the tipping request),
- an order belonging to a *different* customer (identity/ownership test),
- normal refundable items (happy path).

Full fixture matrix: `docs/components/01-database.md` §6.
