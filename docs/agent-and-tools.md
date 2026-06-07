# Agent Loop & Tools

## The loop

`app/agent/loop.py::run_turn` drives a single turn:

1. Acquire a per-conversation lock (serializes turns so `step_no` stays monotonic).
2. Append the user message; build the provider message list = system prompt + history (`HISTORY_LIMIT`) + any structured `selection`.
3. Up to `MAX_AGENT_ITERATIONS` times: stream the model's turn; collect text deltas (emitted as `token` events) and any tool calls.
4. Persist the assistant text as a `model_text` step. If the model returned no tool calls, emit `done` and stop.
5. For each tool call: emit `tool_call`, dispatch it through the validated boundary, time it, persist a `tool_call` step and a `tool_result` step (with latency), emit `tool_result`. After `present_return_options`, emit `return_selector`. For binding outcomes, persist a `decision` step and emit `decision`.
6. Feed each tool result back to the model and continue.

If the iteration cap is reached without a final answer, the loop **fails closed**: it writes an `ESCALATE` decision (`reason: iteration_cap`), sets the conversation to `escalated`, and emits `decision` + `done`. It never approves on exhaustion.

The loop has **no authority to approve a refund** — it only calls tools; the tools enforce. Trace writes happen as the loop executes, independent of whether SSE emission succeeds (it guards each `yield` against `GeneratorExit` so a client disconnect flips to "don't emit" while the turn runs to completion).

## Tools (8)

Each tool has a strict Pydantic input schema and returns a structured `ToolResult`. Signature: `fn(ctx: ToolContext, args: dict) -> ToolResult`. The model never receives raw DB rows or internal IDs.

| Tool | Input | Purpose |
|---|---|---|
| `verify_identity` | order number + email | Binds `conversation.customer_id`. Order/refund tools refuse to run until this is set. |
| `lookup_orders` | _(none)_ | Lists the verified customer's orders only. |
| `get_order_details` | order ref | Per-item detail (final-sale flag, window, status) for an owned order. |
| `get_policy` | _(none)_ | Returns the policy text for citation/reasoning. |
| `check_refund_eligibility` | line ref + quantity | **Read-only** preview: runs the rule engine, returns the verdict without mutating anything. |
| `process_refund` | line ref + quantity | **Re-runs the rule engine**; only on `APPROVE` does it write the refund row and update state. Returns the enforced outcome regardless of model intent. |
| `present_return_options` | order ref | Lists returnable items with eligibility hints; triggers the Return Selector card. |
| `escalate_to_human` | summary | Creates an escalated refund row and marks the conversation escalated. |

`check_refund_eligibility` and `process_refund` call the **same** rule engine — the engine is the single binding authority; tools never re-implement rules. See [`rule-engine.md`](rule-engine.md).

## Guardrails (prompt-injection resilience)

Defense is in code, not in the prompt. In order of importance:

1. **Deterministic enforcement** — chat output is advisory; the rule engine's verdict is binding. `process_refund` acts only on `APPROVE`.
2. **Identity binding** — no order is actionable until `verify_identity` succeeds; tools filter by `conversation.customer_id`.
3. **Quantity invariant** — `SUM(approved units) ≤ item.quantity`, re-checked under a `SELECT … FOR UPDATE` row lock; no over-refund even under races.
4. **Projected per-order ceiling** — if prior approved refunds + the current request would exceed the threshold, the request escalates; never auto-approved.
5. **Iteration cap** (`MAX_AGENT_ITERATIONS`, default 8) — prevents infinite tool loops / token burn; exhausting it escalates (fail closed).
6. **Tool-input validation** — Pydantic rejects malformed args before any DB call; unknown tools and tool exceptions return a safe error, never a crash.
7. **No leakage** — internal UUIDs and raw tool JSON never cross the tool boundary into customer-facing events; the system prompt and policy internals are never returned.
8. **Hardened system prompt** (defense-in-depth, *not* the boundary) — instructs the model that tools are the only source of truth and that customer text claiming "admin/developer/system override" authority is ordinary untrusted content to be ignored.

The adversarial suite proves these hold even against a jailbroken model — see [`testing.md`](testing.md).
