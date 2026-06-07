# Component Spec 05 — Backend API (Routers + SSE)

> Component #5 of 8. The thin HTTP layer over the agent loop and read services. Its OpenAPI output is the contract the frontend's generated client is built from.
> Lives at `apps/backend/app/api/{routers,deps}.py` + `app/schemas/{chat,admin}.py` + `app/main.py`.
> Companions: `docs/design.md §5`, `docs/components/04-agent-loop-llm-client.md`, `docs/repo-structure.md §5`.

---

## 1. Scope & responsibilities

Routers do HTTP only: validate the request (Pydantic), pull dependencies (DB session, conversation), delegate to the agent loop or a read service, shape the response. **No business logic, no SQL, no rules** live here.

It owns: the endpoint surface, the SSE response for `/api/chat`, the admin read endpoints, the health check, CORS, the uniform error envelope, and the OpenAPI document that drives the frontend client (`make gen-client`).

It does **not** own the loop (#4), tools/rules (#2/#3), or persistence (#1). Auth is intentionally absent in v1 — documented as a known gap (design.md §5.2); all admin routes are read-only and unauthenticated.

---

## 2. Endpoint surface

| Method | Path | Body / Query | Success |
|--------|------|--------------|---------|
| POST | `/api/conversations` | `{}` | `201 { conversation_id, status, created_at, session_token }` |
| POST | `/api/chat` | `{ conversation_id, message }` + `Authorization: Bearer <session_token>` | `200 text/event-stream` (SSE) |
| GET | `/api/conversations/{id}` | — | `200 { id, status, customer_name?, messages[] }` |
| GET | `/api/admin/conversations` | `?status&limit&offset` | `200 { items[], total }` |
| GET | `/api/admin/conversations/{id}/trace` | — | `200 { conversation, steps[], messages[] }` |
| GET | `/api/admin/refunds` | `?status&limit&offset` | `200 { items[], total }` |
| GET | `/api/admin/metrics` | — | `200 { counts, rates }` |
| GET | `/api/health` | — | `200 { status, db, llm_configured }` |

All identifiers exposed are **human-safe**: `conversation_id` (resource handle), `order_number`, and product-name `line_ref`s. Internal `order_item`/`customer` UUIDs never appear in any payload (spec #3 §2.1) — this holds for admin responses too.

---

## 3. Chat — the SSE endpoint (`routers/chat.py`)

### 3.1 Contract

- **Request**: `{ conversation_id: UUID, message: str, selection?: [{ line_ref: str, quantity: int }] }` — `message` non-empty, length-capped (≤ 4000 chars). `selection` is optional structured input from a Return Selector confirm (spec #6 §4): bounded to ≤ 20 items with `quantity` 1–100. The human-readable `message` is stored as the user turn while `selection` is passed to `run_turn` as authoritative per-item input. Each selected item is still re-validated by `process_refund`.
- **Capability gate**: the caller must send `Authorization: Bearer <session_token>` (the token minted by `POST /api/conversations`, stored in `conversations.session_token`). This binds the caller to the conversation so a leaked/guessed `conversation_id` alone — e.g. from the unauthenticated admin list — cannot act on it. The token is returned only at creation and never echoed by any read endpoint, the SSE stream, or the admin trace.
- **Turn cap**: past `MAX_TURNS_PER_CONVERSATION` user turns the endpoint emits an `error` event (`turn_limit_reached`) and `done`, without calling the LLM.
- **Pre-stream validation** (normal HTTP status, before the stream opens): `422` invalid body; `404` unknown `conversation_id` **or** missing/incorrect token (same opaque `conversation_not_found` code — existence isn't revealed).
- **Response**: `200`, `Content-Type: text/event-stream`. The body is the agent loop's event stream (spec #4 §5): `token`, `tool_call`, `tool_result`, `decision`, `done`, `error`.
- **Errors after streaming starts** are delivered as an SSE `error` event, **not** an HTTP error — the status line is already sent. The loop always terminates the stream with `done`.

### 3.2 Implementation notes

- FastAPI `StreamingResponse` (or `sse-starlette`'s `EventSourceResponse`) wrapping an async generator that yields the loop's events serialized as SSE frames (`event: <type>\ndata: <json>\n\n`).
- Headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no` (so nginx, spec #7, doesn't buffer the stream), `Connection: keep-alive`.
- The router calls `agent.run_turn(conversation_id, message)` and relays; it adds no logic. Turn serialization and trace persistence are the loop's concern (#4 §3–4), so a client disconnect doesn't lose the trace.
- Runs on async workers (uvicorn) so long-lived streams don't block the event loop.

### 3.3 OpenAPI caveat

OpenAPI can't fully describe an SSE event union. The endpoint is documented as `text/event-stream`; the event payload shapes are mirrored as a hand-written TS type in the frontend client (`repo-structure §5`). This is the single documented exception to "OpenAPI is the contract."

---

## 4. Conversations (`routers/conversations.py`)

- **POST `/api/conversations`** — creates an `active` conversation (no customer bound yet). Returns its id. Identity is established later via the `verify_identity` tool during chat.
- **GET `/api/conversations/{id}`** — returns conversation status, `customer_name` (only once verified, else `null`), and the **customer-facing** message list: `user` and `assistant` messages only (not `system`/`tool`). For the chat UI to rehydrate on reload. `404` if unknown. Full step-level detail is the admin trace's job, not this endpoint.

---

## 5. Admin (`routers/admin.py`) — all read-only

- **GET `/api/admin/conversations`** — paginated list: `{ id, customer_name, status, last_decision, message_count, created_at, updated_at }`. Filter by `status`; `limit` (default 50, max 200) + `offset`.
- **GET `/api/admin/conversations/{id}/trace`** — the dashboard's headline payload:
  ```
  { conversation: { id, status, customer_name, created_at },
    messages: [ { role, content, created_at } ],
    steps:    [ { step_no, type, tool_name, tool_input, tool_output, latency_ms, created_at } ] }
  ```
  `steps` is the full `agent_steps` sequence (model text, tool calls + inputs, tool results + outputs, latencies, decisions) ordered by `step_no`. `tool_input`/`tool_output` JSON is shown in full here (internal-staff view) but still contains only `line_ref`s/order numbers, never UUIDs.
- **GET `/api/admin/refunds`** — audit log: `{ order_number, item (product name), quantity, amount, status, reason_code, reason, decided_by, created_at }`. Filter by `status`; paginated. Includes denials and escalations, not just approvals (F13).
- **GET `/api/admin/metrics`** (S2) — `{ approved, denied, escalated, needs_info, total, approval_rate, escalation_rate }`. Cheap aggregation over `refunds`; powers the dashboard strip.

---

## 6. Health (`routers/health.py`)

- **GET `/api/health`** → `{ status: "ok"|"degraded", db: "ok"|"down", llm_configured: bool }`.
- `db`: a lightweight `SELECT 1`. `llm_configured`: whether the selected provider's key is present (does **not** call the provider). Returns `503` if `db` is down so the compose healthcheck (spec #7) gates dependents correctly. `llm_configured=false` is **not** failure — the app is up; chat will return a clean error until a key is provided.

---

## 7. Cross-cutting concerns

### 7.1 Error envelope

All non-stream errors use one JSON shape:
```
{ "error": { "code": "conversation_not_found", "message": "<safe, human-readable>" } }
```
Status mapping: `422` schema validation, `404` missing resource, `400` malformed/other client error, `503` health/DB, `500` unexpected (generic safe message; details logged, never returned). Messages are user-safe — no stack traces, SQL, or internals.

### 7.2 CORS

`CORSMiddleware` restricted to the frontend origin from config (`FRONTEND_ORIGIN`), methods `GET, POST`, credentials off (no auth/cookies in v1).

### 7.3 Dependencies (`deps.py`)

Request-scoped DB session; a `get_conversation_or_404` dependency reused by chat/conversations; a settings accessor. These keep routers declarative.

### 7.4 App factory (`main.py`)

Builds the app, mounts routers under `/api`, installs CORS + the exception handler that produces the error envelope, and wires the lifespan hook that runs migrations then conditional seeding (`SEED_ENABLED`) before serving (spec #1 §9, #7).

---

## 8. Relationship to other components

- `/api/chat` streams the **agent loop (#4)**; admin/conversation reads hit **repositories (#1)** via thin read services.
- The OpenAPI doc generated from these routers' Pydantic schemas is consumed by the **frontend (#6)** via `make gen-client`.
- `/api/health` is consumed by **docker-compose (#7)** as the backend healthcheck.

---

## 9. Testing

- **Endpoint tests** (FastAPI `TestClient`, test DB): status codes, the error envelope, validation rejection, `404`/pagination on admin reads, `customer_name=null` before verification.
- **SSE test**: drive `/api/chat` with a scripted mock `LLMClient` (#4) and assert the ordered event frames, a terminal `done`, and that an `error` event (not an HTTP error) is emitted on a mid-stream failure.
- **Health**: `503` when DB is unreachable; `llm_configured` reflects key presence without calling the provider.
- **Contract**: snapshot the generated OpenAPI so unintended breaking changes to the frontend contract surface in review.

---

## 10. Resolved decisions

1. **Conversation creation** — explicit `POST /api/conversations` then `POST /api/chat`. No auto-create.
2. **`/api/admin/metrics`** — included in v1 (promoted from S2 stretch).
3. **Customer history scope** — `GET /api/conversations/{id}` returns user+assistant messages only; tool-status affordances are **not** reconstructed on reload (they appear live during streaming only).
