# Component Spec 03 — Tools Layer

> Component #3 of 8. The adapters the agent calls — and the **trust boundary** of the whole system.
> Lives at `apps/backend/app/tools/*` + `apps/backend/app/schemas/tools.py`.
> Companions: `docs/design.md §0, §4.2`, `docs/components/01-database.md`, `docs/components/02-policy-rule-engine.md`.

---

## 1. Scope & responsibilities

Tools are thin, deterministic functions that the agent loop invokes by name. Each one: validates its inputs, enforces identity/ownership, gathers facts from repositories, calls the rule engine where a verdict is needed, performs any state change inside a transaction, and returns a structured, user-safe result.

This is where the system's security lives. **Three enforcement rules are implemented here, in code, not in the prompt:**

1. **The model never supplies identity.** `verified_customer_id` and `conversation_id` come from server-side conversation state (the `ToolContext`), never from tool arguments. An attacker cannot pass someone else's customer id.
2. **The model never supplies money or overrides policy.** `process_refund` computes `amount = unit_price × quantity` itself and re-derives the verdict via `decision()`. Any "amount", "approved", or "ignore the policy" the model emits is irrelevant — those aren't parameters.
3. **Ownership is re-checked at the data layer.** Even with a valid `order_number`, a tool returns *not found* if the order isn't owned by the verified customer (no cross-customer enumeration).

Tools do **not** own business rules (rule engine, #2), the LLM loop (#4), or HTTP concerns (#5).

---

## 2. The trust boundary: `ToolContext`

Every tool receives two things: **(a) a `ToolContext` injected by the agent loop**, and **(b) the model-supplied arguments** validated against a Pydantic schema.

```
ToolContext {                      # server-side, NOT model-controlled
  conversation_id:      UUID
  verified_customer_id: UUID | None   # set only after verify_identity succeeds
  db_session                          # request-scoped
}
```

The split is the point: the model can ask to refund `ORD-1042`, but it cannot assert *who it is*. Identity is established once, server-side, by `verify_identity`, and persisted on the conversation. Every subsequent tool reads it from context.

### 2.1 No internal identifiers cross the boundary

**Internal primary keys (UUIDs) never leave the backend.** Tools never accept or emit `order_item.id` / `customer.id`. Items are referenced by a **user-safe `line_ref`** — a label derived from the product name, made unique within the order. This holds for tool inputs, tool outputs, the customer chat, *and* the admin trace. The backend alone maps `line_ref → order_item` (scoped to the verified customer's order). Consequences: nothing internal can be shown to a customer, and the model can't guess or pass a raw id for an item it never legitimately retrieved.

---

## 3. Tool catalog

All tools return a common envelope so the loop can serialize results and errors uniformly:

```
ToolResult {
  ok:    bool
  data:  object | null          # tool-specific payload (schemas below)
  error: { code: str, message: str } | null   # user-safe, no internals
}
```

Errors are returned as `ToolResult(ok=false, ...)`, **not raised to the model** — the loop appends them as `tool_result` so the model can recover gracefully (e.g., ask the customer to verify). Unexpected exceptions are caught by the loop, logged, and surfaced as a generic safe error.

### 3.1 `verify_identity`
- **Purpose**: establish identity; bind `conversation.customer_id`.
- **Input**: `{ order_number: str, email: str }`
- **Behaviour**: look up the order by `order_number`; confirm `customers.email` matches (case-insensitive). On match, set `conversation.customer_id` and return minimal confirmation. On mismatch, return `ok=false` (`code=verification_failed`) with a generic message — **do not reveal** whether the order or email existed (anti-enumeration).
- **Output**: `{ verified: true, customer_name }`
- **Notes**: the only tool that may run without a verified context. Re-verification to a *different* customer mid-conversation is rejected (a conversation is bound to one identity).

### 3.2 `lookup_orders`
- **Purpose**: list the verified customer's orders.
- **Input**: `{}`
- **Gate**: requires `verified_customer_id`; else `ok=false` (`code=identity_required`).
- **Output**: `[{ order_number, status, ordered_at, total_amount, currency, item_count }]` — for the verified customer only.

### 3.3 `get_order_details`
- **Purpose**: per-item detail needed to reason about a refund.
- **Input**: `{ order_number: str }`
- **Gate**: identity required; **ownership re-checked** — if the order isn't the verified customer's, return `ok=false` (`code=order_not_found`), same as a truly missing order.
- **Output**: per item —
  ```
  { line_ref, product_name, category, unit_price, quantity,
    is_final_sale, return_window_days, delivered_at,
    refunded_quantity, remaining_quantity,         # derived from refunds
    refund_state }                                  # none | partial | full
  ```
  Plus an order-level `derived_refund_state` (none/partial/full) and `refunded_total` (for the customer's awareness; the threshold itself is enforced server-side). **No `id` or `sku` UUIDs** — `line_ref` is the only handle.
- **`line_ref` construction**: the product name, made unique within the order. If two lines share a name, append a short user-safe qualifier (variant, or a positional suffix like `"Blue Mug (2)"`) — never an internal id. The same string is what the agent speaks to the customer and what it passes to the refund tools, so chat, tool calls, and the admin trace all stay in human terms.
- **Disambiguation**: if a refund tool receives a `line_ref` that resolves to more than one item (should not happen given unique construction, but guarded), it returns `ok=false (code=ambiguous_item)` asking the agent to re-fetch details and use a specific label.

### 3.4 `get_policy`
- **Purpose**: give the model the prose policy to reason with and cite.
- **Input**: `{}`
- **Output**: `{ version, body_markdown }` — the current `policy_documents` row. No identity required (policy is not customer data).

### 3.5 `check_refund_eligibility` (read-only preview)
- **Purpose**: let the agent preview and explain an outcome *before* acting. **Exposed to the model** (confirmed) so it can check and explain eligibility before committing.
- **Input**: `{ order_number: str, line_ref: str, quantity: int }`
- **Gate**: identity + ownership.
- **Behaviour**: gather live facts (item, `already_refunded_qty`, `prior_order_refunded`, any prior denial), call `decision(...)`. **No writes, no locks.**
- **Output**: the `Decision` (outcome, reason_code, message, policy_refs, quantity, amount, dispute_email).
- **Notes**: because it shares `decision()` with `process_refund`, the preview matches the action — modulo concurrent changes, which `process_refund` resolves under lock.

### 3.6 `process_refund` (the state-changing core)
- **Purpose**: make a binding refund decision for N units of one item and record it.
- **Input**: `{ order_number: str, line_ref: str, quantity: int }`
- **Gate**: identity + ownership.
- **Transaction (the critical sequence):**
  1. `BEGIN`.
  2. Resolve `line_ref → order_item` within the verified customer's order, then `SELECT ... FOR UPDATE` on that `order_item` row (and its order) — serializes concurrent requests for the same item.
  3. Re-validate ownership in code (`order.customer_id == ctx.verified_customer_id`).
  4. Re-read live facts under the lock: `already_refunded_qty = SUM(approved units)`, `prior_order_refunded = SUM(approved amount for order)`, plus any existing terminal denial for the item.
  5. **Re-request guard**: if a prior terminal `DENY` exists for this item and the request is the same denied ask, return that denial + `dispute_email` without re-deciding (DB spec §8). A request for still-available units is *not* a denied re-attempt and proceeds.
  6. Call `decision(...)` with the live facts and injected `now`.
  7. Persist a `refunds` row matching the outcome:
     - `APPROVE` → `status=approved`, `quantity`, `amount=unit_price×quantity` (consumes units); re-assert the quantity invariant after computing.
     - `DENY` → `status=denied` (consumes nothing).
     - `ESCALATE` → `status=escalated`; set `conversation.status=escalated`.
     - `NEEDS_INFO` → **no row**; return the decision so the agent can ask for the missing input.
  8. `COMMIT`.
- **Output**: the `Decision`.
- **Hard guarantees**: amount is computed, never model-supplied; the verdict is re-derived under lock; the quantity invariant (DB §7) is enforced post-decision so no over-refund is possible even under races.

### 3.7b `present_return_options` (return-selector discovery)
- **Purpose**: produce the data the frontend renders as the interactive **Return Selector** (spec #6 §4); the agent calls this when a customer wants to return items.
- **Input**: `{ order_number: str }`
- **Gate**: identity + ownership (returns `order_not_found` otherwise).
- **Behaviour**: read-only. Lists the order's line items with `remaining_quantity > 0`, each annotated with a **server-computed eligibility hint** by running the rule engine in preview mode (same `decision()` as `check_refund_eligibility`, but per item for `remaining_quantity` units, no writes/locks). Excludes fully-returned items.
- **Output** (consumed by the `return_selector` SSE event):
  ```
  { order_number,
    items: [ { line_ref, product_name, unit_price, remaining_quantity,
               eligibility: "eligible"|"final_sale"|"window_expired"|"not_delivered",
               eligibility_note } ],
    threshold_usd, already_refunded_total }
  ```
- **Authority note**: `eligibility` is a UI hint only. The binding check still happens in `process_refund` at confirm time — a hint can never grant a refund the rule engine would deny. No internal ids; `line_ref` only.

### 3.7 `escalate_to_human`
- **Purpose**: explicit hand-off when the rule engine returns `ESCALATE`, or for genuine ambiguity the agent can't resolve.
- **Input**: `{ order_number: str, line_ref: str | null, summary: str }`
- **Gate**: identity + ownership.
- **Behaviour**: idempotent — if the item already has an `escalated` refund row, return it rather than duplicating; otherwise record one and mark the conversation `escalated`.
- **Output**: `{ escalated: true, reference }`.
- **Notes**: v1 simply **records the escalation and tells the customer** (confirmed). "Human handling" is out of scope (design.md non-goals) — no live agent is paged, no notification stub is emitted.

---

## 4. Granularity: one item per call

Each refund/eligibility call targets **one line item**. A multi-item request ("refund my whole order") is handled by the agent looping `process_refund` per item — each producing its own trace step and its own outcome. Rationale: clean, auditable per-item traces; the per-order threshold is still correct because `prior_order_refunded` is re-read each call inside the lock, so the item that tips the order over $500 escalates while earlier ones approve. (A batch tool is possible later but muddies the trace and the threshold attribution — deferred.)

---

## 5. Enforcement matrix (what stops each attack)

| Attack / mistake | Stopped by |
|------------------|-----------|
| "I'm customer X, refund their order" | model can't set identity; `ToolContext` is server-side (§2) |
| Spoof `customer_id` as a tool arg | not a parameter of any tool |
| "Approve a $900 refund anyway" | `amount` not a parameter; `decision()` re-derived; threshold → ESCALATE |
| "Ignore the policy / final sale" | policy enforced in `decision()`, not the prompt; tool calls it regardless |
| Refund a final-sale item | `decision()` step 4 → DENY |
| Split refund to dodge $500 | `prior_order_refunded` re-read per call → projected total escalates |
| Double-refund / race | `SELECT FOR UPDATE` + quantity invariant re-check |
| Enumerate other customers' orders | ownership re-check returns `order_not_found` |
| Guess/pass a raw item id | tools take `line_ref` only; UUIDs never exposed (§2.1) |
| Re-ask after denial | re-request guard returns prior denial + dispute email |

This table is the resilience story for the eval; the adversarial suite (spec #8) tests each row.

---

## 6. Schemas & registration

- Every tool's input/output is a Pydantic model in `schemas/tools.py`; these generate the JSON tool schemas the LLM sees (spec #4 registry) and keep validation and the model's contract in one place.
- Inputs are validated **before** any DB access; a schema failure returns `ok=false (code=invalid_input)` with a safe message.
- Tools call **services** (`refund_service`, `customer_service`, `policy_service`) which call **repositories** — tools never write raw SQL or embed rules.

---

## 7. Testing

- **Unit** (mocked repos): each gate (identity_required, order_not_found), input validation, the envelope shape, and that `process_refund` ignores any stray model-supplied fields.
- **Integration** (test DB): the `process_refund` transaction — partial-quantity sequence, threshold accumulation across calls, concurrent-request serialization (two parallel calls, assert no over-refund), re-request-after-denial guard.
- **Security**: the enforcement matrix (§5) row by row — these graduate into the adversarial suite (#8).

---

## 8. Resolved decisions

1. **Line-item handle** — a user-safe `line_ref` (product name, uniqued within the order). Internal UUIDs never cross the tool boundary, into chat, or into the admin trace (§2.1, §3.3).
2. **`check_refund_eligibility`** — exposed to the model so it can preview and explain before acting.
3. **Escalation hand-off** — records the escalation and informs the customer only; no notification stub, no live paging.
