# Component Spec 06 — Frontend (Chat + Admin)

> Component #6 of 8. The React + Vite SPA: customer chat (with an interactive **Return Selector**) and the admin reasoning dashboard.
> Lives at `apps/frontend/`.
> Companions: `docs/design.md §6`, `docs/components/05-backend-api.md`, `docs/repo-structure.md §4`.

---

## 1. Scope & responsibilities

A single SPA, two routes, one API client. It renders the customer conversation (consuming the `/api/chat` SSE stream) and the admin dashboard (the reasoning trace, refund audit, and metrics). It contains **no business logic** — eligibility, decisions, and authorization all live server-side; the UI only displays state and collects input.

Stack: React + Vite + TypeScript, Tailwind, React Query for admin reads, a generated OpenAPI client + a hand-written SSE helper for chat. Routes: `/chat`, `/admin`.

---

## 2. API layer (`src/api`)

- `generated/schema.ts` — raw `openapi-typescript` output, generated from the backend OpenAPI (`make gen-client`). Never hand-edited.
- `types.ts` — the **contract bridge**. It re-exports the REST request/response types from `generated/schema.ts` (`components["schemas"][…]`) under the names the app uses — a few differ from the backend class names (`SelectionItem`→`Selection`, `RefundOut`→`RefundItem`, `ConversationListItem`→`AdminConversationItem`, `ConversationList`→`AdminConversationList`). It also **hosts the hand-written SSE event union** (`SSEEvent` and its `ReturnSelectorPayload` / `DecisionPayload` / `ReturnItem` / `Eligibility` payloads), which mirror `agent/events.py` — the one part of the API OpenAPI can't describe (an event stream is not a REST body, so it has no schema component to alias).
- `client.ts` — thin wrapper over `types.ts`: base URL (`VITE_API_BASE_URL`), error normalization, and the **SSE helper** for `/api/chat`.
- The SSE helper opens the stream via `fetch` + `ReadableStream` (POST body needed, so not `EventSource`), parses `event:/data:` frames, and dispatches typed events to the chat hook.

Because the REST types are *derived* from the generated schema rather than authored, a backend schema change followed by `make gen-client` surfaces any drift as a TypeScript compile error in the consumers, not a silent mismatch. Regenerate after any backend schema change.

---

## 3. Chat feature (`features/chat`)

### 3.1 Components

- `ChatPage` — owns `conversation_id` (created via `POST /api/conversations` on first send), renders the window + composer.
- `ChatWindow` — scrolling message list.
- `MessageBubble` — user / assistant text.
- `ToolStatus` — the lightweight live affordance ("Checking your order…") derived from `tool_call` events (live only; not reconstructed on reload, per API spec §10).
- `DecisionBadge` — APPROVED / DENIED / ESCALATED / NEEDS_INFO, colored, rendered from the `decision` event.
- `Composer` — text input; disabled while a turn is streaming.
- **`ReturnSelector`** — the interactive item-selection table (§4).
- `useChatStream` — the streaming brain: sends a turn, consumes SSE, appends tokens, surfaces tool status, renders a `ReturnSelector` when a `return_selector` event arrives, flips the badge on `decision`, ends on `done`, shows a message on `error`.

### 3.2 SSE event → UI mapping

| event | UI effect |
|-------|-----------|
| `token` | append delta to the streaming assistant bubble |
| `tool_call` | show/refresh `ToolStatus` |
| `tool_result` | clear/advance `ToolStatus` |
| `return_selector` | render a `ReturnSelector` card inline (§4) |
| `decision` | render/update `DecisionBadge` for that item |
| `done` | finalize the bubble, re-enable composer |
| `error` | show a non-technical error line, re-enable composer |

`return_selector` is a **new event** (backend touchpoint — §7) carrying the returnable-items payload.

---

## 4. The Return Selector (the requested feature)

### 4.1 Trigger & flow

1. Customer expresses return intent; the agent verifies identity if needed.
2. The agent calls a new tool **`present_return_options(order_number)`** (#3 touchpoint) whose result is the selector payload. The loop emits it as a `return_selector` SSE event (#4 touchpoint).
3. The frontend renders the interactive card inline in the conversation.
4. Customer picks items + quantities and clicks **Confirm**.
5. The confirm posts a **structured selection** to `/api/chat` (#5 touchpoint): `{ conversation_id, message, selection: [{ line_ref, quantity }] }`. `message` is a human-readable echo ("Return 1 × Blue Mug, 2 × Red Hat — ORD-1042") for the transcript; `selection` is the deterministic, authoritative input the agent acts on.
6. The agent calls `process_refund` once per selected item; each is **re-validated** server-side and produces its own `decision` event. The card disables itself after submit.

This avoids re-parsing free text: what the customer picked is passed structurally, so there's no ambiguity between the widget and what gets refunded.

### 4.2 Payload shape (from `present_return_options`)

```
{ order_number,
  items: [ { line_ref, product_name, unit_price, remaining_quantity,
             eligibility: "eligible" | "final_sale" | "window_expired" | "not_delivered",
             eligibility_note } ],
  threshold_usd, already_refunded_total }
```

`eligibility` is a **hint computed server-side** to drive the UI (enable/disable, explain) — it is *not* the authority. `process_refund` re-derives the verdict at confirm time; a hint can never grant a refund the rule engine would deny.

### 4.3 The table

| col | content |
|-----|---------|
| select | checkbox; **disabled** for non-`eligible` rows |
| item | `product_name` (never an internal id) |
| unit price | formatted money |
| available | `remaining_quantity` |
| quantity | dropdown `1..remaining_quantity`, enabled only when the row is checked |
| note | for ineligible rows: the reason ("Final sale — not returnable", "Return window closed", "Not yet delivered") |

Below the table: a **running refund total** of checked rows, a **"may require human review" hint** if the projected total (`already_refunded_total + selection`) would exceed `threshold_usd` (transparency, not a block), and the **Confirm** button (disabled until ≥1 eligible row is checked).

### 4.4 Item visibility & edge cases

- **Fully-returned items are excluded** (`remaining_quantity = 0` not listed).
- **Ineligible-but-listable items** (final sale / window expired / not delivered) are **shown but disabled with the reason** — transparency beats a mystery omission, and it preempts "why can't I return X?".
- **Stale card**: after Confirm, the card is locked (read-only). If items were returned elsewhere in the meantime, the server's re-validation at confirm is authoritative and the resulting `decision` events tell the true story.
- **Reload mid-selection**: the card is live UI, not persisted as a renderable message (consistent with "don't reconstruct affordances"); on reload the customer simply re-asks. Documented limitation.
- **Over-threshold selection**: allowed to submit; the tipping item escalates server-side and the customer sees an ESCALATED badge — the hint just warned them first.

---

## 5. Admin feature (`features/admin`)

- `AdminPage` — layout + `MetricsBar`.
- `ConversationList` — table from `GET /api/admin/conversations` (id, customer, status, last decision, time); filter by status; row → detail.
- `TraceTimeline` — the headline view: vertical timeline from `GET /api/admin/conversations/{id}/trace`. One `StepCard` per `agent_step`.
- `StepCard` — renders a step by type: model text, `tool_call` (name + input JSON), `tool_result` (output JSON), latency, `decision` (outcome + policy refs). Full JSON shown (internal view) — still no UUIDs, only `line_ref`s/order numbers.
- `RefundTable` — `GET /api/admin/refunds` audit (order, item name, qty, amount, status, reason, decided_by, time); status filter; includes denials/escalations.
- `MetricsBar` — counts + approval/escalation rates from `GET /api/admin/metrics`.

Admin reads use React Query with a manual refresh (the view header's Reload); no auto-poll needed in v1.

---

## 6. Cross-cutting

- **State**: chat is local component state + the streaming hook; admin is React Query server state. No global store needed.
- **Loading / empty / error**: every fetch and the stream have explicit states; the composer is disabled during a streaming turn; errors render as plain language.
- **Styling**: Tailwind core utilities; feature-foldered components; shared primitives in `components/`.
- **Accessibility**: the Return Selector is a real `<table>` with labeled checkboxes and selects, keyboard-operable, disabled rows marked `aria-disabled` with the reason as accessible text.

---

## 7. Backend touchpoints this feature requires (to retrofit after your confirmation)

The Return Selector adds these to earlier specs — **proposed, pending your go-ahead** before I edit those docs:

1. **#3 Tools** — new `present_return_options(order_number)` tool returning the §4.2 payload (returnable items + server-computed eligibility hints). Read-only, identity+ownership gated.
2. **#4 Agent loop** — new SSE event `return_selector`; and `run_turn` accepts an optional structured `selection` that drives `process_refund` calls deterministically.
3. **#5 API** — `/api/chat` request body gains optional `selection: [{ line_ref, quantity }]`; the human-readable `message` is still stored as the user turn.
4. **#1 DB** — no schema change: the selection is rendered to user-message text + passed transiently to the loop and logged in `agent_steps`; nothing new persisted.

Authority is unchanged: `process_refund` re-validates every selected item; the widget and its eligibility hints are convenience only.

---

## 8. Testing (Vitest + Testing Library)

- `useChatStream`: feed a scripted SSE sequence (token → tool_call → return_selector → decision → done); assert bubbles, status, the rendered selector, and the badge.
- `ReturnSelector`: disabled ineligible rows; quantity capped at `remaining_quantity`; running total; over-threshold hint; Confirm posts the exact `selection`; locks after submit.
- Admin: `TraceTimeline` renders each step type; `RefundTable`/`MetricsBar` from fixture payloads.
- A snapshot against the committed generated client to catch contract drift.

---

## 9. Resolved decisions

1. **Backend touchpoints (§7)** — approved and retrofitted into specs #3 (`present_return_options` tool), #4 (`return_selector` SSE event + structured `selection` in `run_turn` + system-prompt directive), #5 (`selection` on `/api/chat`). DB unchanged.
2. **Ineligible items** — shown in the table, disabled, with the reason as accessible text.
3. **Selector usage** — always used for returns (the system prompt directs the agent to call `present_return_options` first), for consistency.
