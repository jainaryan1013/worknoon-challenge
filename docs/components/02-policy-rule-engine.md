# Component Spec 02 — Policy & Rule Engine

> Component #2 of 8. The **binding decision authority**: the deterministic function that decides every refund outcome.
> Lives at `apps/backend/app/services/rule_engine.py` + `apps/backend/app/seed/policy_source.py`.
> Companions: `docs/design.md §0, §4.3`, `docs/components/01-database.md`.
>
> **Model: decisions are made per line item, per request, for a specific quantity of units.** Items are evaluated independently. The $500 escalation threshold is applied per order, on the projected cumulative refund, before confirming.

---

## 1. Scope & responsibilities

This component answers one question: **given the facts about a refund request for N units of one line item, what is the outcome?**

It provides:

- `decision(...)` — a **pure, deterministic function**. No DB, no LLM, no I/O, no side effects.
- The **policy source of truth** (`policy_source.py`) from which both the prose policy doc and `policy_rules` are generated.
- The reason-code vocabulary and human messaging (including the denial → dispute-email off-ramp).

It does **not** read the database or mutate state. Tools (spec #3) gather facts, call `decision()`, and act on its output. The engine is trivially unit-testable and is the single place a refund verdict is produced.

**Core principle (design.md §0):** the LLM orchestrates; this function authorizes. `process_refund` writes an approved refund only when this function returns `APPROVE`, and re-derives the verdict itself — it never trusts a verdict suggested by the model.

---

## 2. Outcomes

| Outcome | Meaning | Downstream effect |
|---------|---------|-------------------|
| `APPROVE` | Eligible; refund the requested units of this item | writes approved refund (consumes units, moves money) |
| `DENY` | Permanently ineligible | writes denied refund (terminal for this item/reason); agent gives reason + dispute email |
| `ESCALATE` | Eligible but the request pushes the order's projected refund over $500 | writes escalated refund, conversation → `escalated`, hands to human |
| `NEEDS_INFO` | Cannot decide yet (item not delivered) or request is malformed | **no refund row written**; agent explains the missing precondition |

Only `APPROVE`/`DENY`/`ESCALATE` write a `refunds` row. `NEEDS_INFO` is non-terminal and writes nothing.

---

## 3. The `decision()` contract

### 3.1 Signature (language-neutral)

```
decision(
  item:                 { id, order_id, is_final_sale, return_window_days,
                          unit_price, quantity, delivered_at }
  requested_quantity:   int                    # units the customer wants refunded now
  already_refunded_qty: int                    # approved units already refunded for this item
  order_owner_id:       UUID                    # item.order.customer_id
  verified_customer_id: UUID | None             # from conversation; None = not verified
  prior_order_refunded: Decimal                 # SUM(approved refund amount) for the order so far
  existing_denial:      Decision | None         # prior terminal denial for this item, if any
  rules:                PolicyRules             # loaded from policy_rules
  now:                  datetime (UTC)          # injected, never read internally
) -> Decision
```

`now` is injected for deterministic time tests. Facts are supplied by the caller; the engine performs no lookups.

### 3.2 Return type

```
Decision {
  outcome:       APPROVE | DENY | ESCALATE | NEEDS_INFO
  reason_code:   ReasonCode
  message:       str                   # human-readable, safe to show the customer
  policy_refs:   [str]                 # rule keys / clauses that applied
  quantity:      int                   # units this decision covers (= requested_quantity)
  amount:        Decimal               # item.unit_price * quantity (for APPROVE/ESCALATE)
  dispute_email: str | None            # set on DENY only, from rules.dispute_email
}
```

### 3.3 ReasonCode vocabulary

```
APPROVED
DENIED_NOT_OWNER            # verified customer != order owner, or not verified
DENIED_FINAL_SALE
DENIED_WINDOW_EXPIRED
DENIED_FULLY_REFUNDED       # no units remain on the item
ESCALATED_OVER_THRESHOLD    # projected per-order refund > $500
NEEDS_INFO_NOT_DELIVERED
NEEDS_INFO_INVALID_QUANTITY # requested <= 0 or exceeds remaining units
```

---

## 4. Evaluation order (precedence) — the heart of the spec

A **single line item** is evaluated. Checks run in a fixed order; first match wins and sets the primary `reason_code`. Order is by *severity and knowability*:

```
remaining = item.quantity - already_refunded_qty

1. OWNERSHIP        if verified_customer_id is None OR != order_owner_id
                        -> DENY (DENIED_NOT_OWNER)
2. FULLY REFUNDED   if remaining <= 0
                        -> DENY (DENIED_FULLY_REFUNDED)
3. VALID QUANTITY   if requested_quantity <= 0 OR requested_quantity > remaining
                        -> NEEDS_INFO (NEEDS_INFO_INVALID_QUANTITY)
4. FINAL SALE       if item.is_final_sale and rules.final_sale_refundable is False
                        -> DENY (DENIED_FINAL_SALE)
5. NOT DELIVERED    if item.delivered_at is None
                        -> NEEDS_INFO (NEEDS_INFO_NOT_DELIVERED)
6. WINDOW           if days_between(item.delivered_at, now) > item.return_window_days
                        -> DENY (DENIED_WINDOW_EXPIRED)
7. THRESHOLD        amount = item.unit_price * requested_quantity
                    if prior_order_refunded + amount > rules.escalation_threshold_usd
                        -> ESCALATE (ESCALATED_OVER_THRESHOLD)
8. otherwise        -> APPROVE (APPROVED)
```

### Why this order

- **Ownership first** — security gate; a non-owner learns nothing about the item. Primary injection defense.
- **Fully-refunded second** — current state dominates; nothing to do if no units remain.
- **Valid-quantity third** — reject malformed requests (≤0 or more than remaining) as `NEEDS_INFO` before evaluating policy, so the customer can correct rather than receive a misleading denial.
- **Final-sale before not-delivered** — final sale is a *terminal, immediately-knowable* no; don't tell a customer to wait for delivery only to deny later.
- **Not-delivered before window** — you can't compute "window expired" without a delivery date; avoids `days_between(None, now)`.
- **Threshold last** — escalation applies only to an *otherwise-eligible* refund, and uses the **projected per-order total** (`prior_order_refunded + this amount`), so a large first request or an accumulation across the order both escalate the request that crosses $500. This is checked before confirmation (no refund is written for an escalated request).

`policy_refs` records every clause relevant to the verdict; `reason_code` names the first match.

### Per-item independence

There is **no cross-item logic** here. Each item is judged on its own delivery, window, and final-sale flag. The only order-level input is `prior_order_refunded`, used solely for the threshold. An order with a refundable item and a final-sale item produces an APPROVE for one and a DENY for the other.

---

## 5. Policy source of truth (`policy_source.py`)

Defines the rule constants once:

```
ESCALATION_THRESHOLD_USD   = 500
DEFAULT_RETURN_WINDOW_DAYS = 30
FINAL_SALE_REFUNDABLE      = False
DISPUTE_EMAIL              = "disputes@refundagent.example"   # placeholder, TBD
```

From these it produces, at seed time: (1) the `policy_rules` rows the engine loads, and (2) `policy_documents.body_markdown` rendered from a template interpolating the same constants. **Anti-drift guarantee**: both derive from one run, so prose and enforcement can't disagree.

`item.return_window_days` is authoritative per item; `DEFAULT_RETURN_WINDOW_DAYS` is only the fallback when an item has no window set (the DB column defaults to 30, so this is a belt-and-suspenders default).

### Rule loading & caching

The engine receives `rules` as an argument (purity). `policy_service` loads `policy_rules` into a typed `PolicyRules` object, cached per process. A missing/renamed key fails loudly at load, not silently mid-decision.

---

## 6. Failure modes (fail closed)

Never produce a false `APPROVE` under degraded conditions:

- **Missing/unparseable rule** → `policy_service` raises at load; the tool converts to `ESCALATE` (route to human), never `APPROVE`.
- **`verified_customer_id is None`** → always `DENY` at step 1.
- **Inconsistent quantity data** (`already_refunded_qty > item.quantity`) → `remaining < 0` → step 2 `DENY (FULLY_REFUNDED)`; never approve.
- **Non-positive `unit_price`** → still evaluated; a $0 line can approve only if otherwise eligible, flagged in `policy_refs`.

Guiding rule: any ambiguity resolves *away from* auto-approval.

---

## 7. Relationship to other components

- **Tools (spec #3)** gather inputs from repositories, call `decision()`, and act:
  - `check_refund_eligibility(order_item, qty)` → calls `decision()`, returns it read-only (no writes). Lets the agent preview/explain.
  - `process_refund(order_item, qty)` → under a row lock on the item, re-reads `already_refunded_qty` and `prior_order_refunded`, re-calls `decision()`, then writes a refund row matching the outcome. Only `APPROVE` consumes units / moves money. **Re-derives the verdict; never trusts the model's claim.**
  - `escalate_to_human(...)` → used when outcome is `ESCALATE`.
- **Agent (spec #4)** turns `Decision.message` + `dispute_email` into customer-facing text; surfaces the dispute email on `DENY`; may call the eligibility check per item before acting on a multi-item request.
- **DB (spec #1)** supplies fact shapes, the quantity invariant the threshold/consumption rely on, and the `refunds` row each outcome maps to.

`check_*` and `process_*` call the **same** `decision()`, so "previewed" and "actually happened" cannot diverge — except that `process_*` re-reads live quantity/threshold inside the lock, which is the authoritative evaluation.

---

## 8. Testing (exploit the purity)

Table-driven unit tests, no DB. One per branch + boundaries:

| Test | Input | Expect |
|------|-------|--------|
| no identity / wrong owner | verified None or ≠ owner | DENY / NOT_OWNER |
| fully refunded | already_refunded_qty = quantity | DENY / FULLY_REFUNDED |
| invalid qty (zero) | requested 0 | NEEDS_INFO / INVALID_QUANTITY |
| invalid qty (over remaining) | requested 5, remaining 2 | NEEDS_INFO / INVALID_QUANTITY |
| final sale | item final | DENY / FINAL_SALE |
| final sale + not delivered | both | DENY / FINAL_SALE (precedence) |
| not delivered | delivered_at None, eligible | NEEDS_INFO / NOT_DELIVERED |
| window expired | delivered now-60d, window 30 | DENY / WINDOW_EXPIRED |
| **boundary: exactly window** | delivered now-30d, window 30 | APPROVE (`>` not `>=`) |
| over threshold (single big) | prior 0, amount 600 | ESCALATE / OVER_THRESHOLD |
| over threshold (accumulated) | prior 400, amount 150 | ESCALATE / OVER_THRESHOLD |
| **boundary: exactly $500** | prior 0, amount 500.00 | APPROVE (`>` not `>=`) |
| **boundary: prior 450 + 50** | projected 500.00 | APPROVE |
| partial approve | remaining 3, requested 1, under threshold | APPROVE qty=1 |
| happy path | eligible, projected ≤ 500 | APPROVE |
| degraded rules | rules fail to load | not APPROVE (escalate) |

These cases are the executable specification of policy and feed directly into the adversarial suite (spec #8) — notably the threshold-evasion attempts (splitting a refund across items/quantities), which the per-order projected check defeats.

---

## 9. Resolved decisions

1. **Granularity** — per item, per request, per quantity.
2. **Window** — each item uses its own window from its own delivery; no cross-item min/max.
3. **Threshold** — per order, on `prior_order_refunded + current amount`, tested before confirming; defeats split-to-evade.
4. **Not-delivered** — `NEEDS_INFO` (re-evaluable after delivery), not a denial.
5. **Invalid quantity** — `NEEDS_INFO` so the customer can correct, not a denial.
6. **Denial re-requests** — deterministic; tool returns the prior denial and points to `dispute_email`; new requests on still-available units are allowed.
