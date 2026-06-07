# Rule Engine

`app/services/rule_engine.py::decision()` is the **single binding authority** on every refund. It is a pure, deterministic function: no DB, no LLM, no I/O, no side effects. Tools gather facts, call it, and act on the result. The model's chat output is advisory; this function's output is binding, and `process_refund` writes a refund only on `APPROVE`.

`now` is injected as a parameter (for deterministic time tests), never read internally.

## Outcomes

| Outcome | Meaning |
|---|---|
| `APPROVE` | Refund the requested units. |
| `DENY` | Refusal — terminal within the chat (a dispute email is supplied). |
| `ESCALATE` | Route to a human (over the per-order threshold). |
| `NEEDS_INFO` | Re-evaluable once the customer supplies a missing precondition. |

## Evaluation precedence (first match wins)

The order is intentional — security and current state dominate; immediately-knowable "no" answers precede conditional ones.

1. **Ownership** → `DENY` (`DENIED_NOT_OWNER`). `verified_customer_id` must equal the order owner. A non-owner learns nothing about the item. Security gate, checked first.
2. **Fully refunded** → `DENY` (`DENIED_FULLY_REFUNDED`). Remaining units (`quantity − already_refunded`) ≤ 0.
3. **Valid quantity** → `NEEDS_INFO` (`NEEDS_INFO_INVALID_QUANTITY`). Requested quantity must be between 1 and remaining; otherwise asks the customer to correct it.
4. **Final sale** → `DENY` (`DENIED_FINAL_SALE`). When `is_final_sale` and policy says final sale is not refundable.
5. **Not delivered** → `NEEDS_INFO` (`NEEDS_INFO_NOT_DELIVERED`). `delivered_at` is NULL; the window can't start yet.
6. **Window** → `DENY` (`DENIED_WINDOW_EXPIRED`). Measured from **that item's own** `delivered_at`. Inclusive of the last day: an item delivered exactly `return_window_days` ago is still eligible (`>`, not `>=`).
7. **Threshold** → `ESCALATE` (`ESCALATED_OVER_THRESHOLD`). When `prior_order_refunded + amount` is **strictly greater than** `escalation_threshold_usd`. Exactly at the threshold still approves.
8. **Approve** → `APPROVE` (`APPROVED`).

A prior terminal denial passed in by the tool is re-affirmed unchanged (denials are deterministic and final in chat). `amount = unit_price × requested_quantity`, quantized to cents.

## Reason codes

`APPROVED`, `DENIED_NOT_OWNER`, `DENIED_FINAL_SALE`, `DENIED_WINDOW_EXPIRED`, `DENIED_FULLY_REFUNDED`, `ESCALATED_OVER_THRESHOLD`, `NEEDS_INFO_NOT_DELIVERED`, `NEEDS_INFO_INVALID_QUANTITY`.

## Policy constants

Defined once in `app/seed/policy_source.py` and used to generate **both** the prose policy doc and the structured `policy_rules`, so text and enforcement never drift.

| Key | Value | Meaning |
|---|---|---|
| `escalation_threshold_usd` | `500` | Projected per-order total strictly above this escalates. |
| `default_return_window_days` | `30` | Fallback window when an item carries none. |
| `final_sale_refundable` | `false` | Final-sale items are never refundable. |
| `dispute_email` | `disputes@refundagent.example` | Address returned on a denial for asynchronous dispute. |

Policy version: `1`. The threshold is evaluated on the **projected cumulative refund per order** (prior approved on the order + current request), computed before the refund is confirmed. Authoritative spec: `docs/components/02-policy-rule-engine.md`.
