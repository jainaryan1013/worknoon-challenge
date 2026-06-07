# API Reference

All routes are mounted under the `/api` prefix. Interactive OpenAPI docs: http://localhost:8000/docs. CORS allows the single `FRONTEND_ORIGIN`, methods `GET` and `POST` only. Admin routes are read-only (no auth in v1 — see [`known-gaps.md`](known-gaps.md)).

## Conversation lifecycle

### `POST /api/conversations`

Start a conversation. Returns **201**.

```json
{ "conversation_id": "<uuid>", "status": "active", "created_at": "<iso8601>", "session_token": "<opaque>" }
```

`session_token` is a per-conversation capability token. It is returned **only here** — never by any read endpoint, the SSE stream, or the admin trace. The client must keep it and present it on every `POST /api/chat` for this conversation (see below). This binds the caller to the conversation: a leaked or guessed `conversation_id` alone cannot act on it.

### `GET /api/conversations/{conversation_id}`

Customer-facing history (user + assistant turns only). **404** if not found.

```json
{
  "id": "<uuid>",
  "status": "active | resolved | escalated",
  "customer_name": "string | null",
  "messages": [ { "role": "user|assistant", "content": "string|null", "created_at": "<iso8601>" } ]
}
```

## Chat (SSE)

### `POST /api/chat`

Runs one agent turn and streams the result as `text/event-stream`. Validation happens before the stream opens: a missing conversation **or a missing/incorrect capability token** returns a normal **404** (`conversation_not_found` — the same opaque code either way, so existence isn't revealed); a malformed body returns **422** (`validation_error`).

**Authorization:** required header `Authorization: Bearer <session_token>`, where the token is the one returned by `POST /api/conversations`. Without a matching token the request is rejected (404) before any work.

Request body:

```json
{
  "conversation_id": "<uuid>",
  "message": "string (1–4000 chars)",
  "selection": [ { "line_ref": "Product Name", "quantity": 2 } ]
}
```

`selection` is optional — it carries the structured items chosen in the Return Selector card back to the agent. It is bounded: **at most 20 items**, each `quantity` in **1–100** (the tool layer re-validates quantity against the order regardless). Conversations are also capped at `MAX_TURNS_PER_CONVERSATION` user turns; past the cap, chat returns an `error` event (`turn_limit_reached`) without calling the model.

#### SSE events

Each event is `event: <type>\ndata: <json>\n\n`. Customer-facing payloads carry **no** internal IDs or raw tool JSON — that split is enforced when building payloads, not left to the model.

| Event | Payload | Meaning |
|---|---|---|
| `token` | `{ "text": "..." }` | An assistant text delta. |
| `tool_call` | `{ "tool": "...", "summary": "..." }` | A tool is running; `summary` is a user-safe status line (e.g. "Checking eligibility…"). |
| `tool_result` | `{ "tool": "...", "status": "ok | <error_code>" }` | The tool finished. |
| `return_selector` | `{ ... }` | The interactive item-selection card (emitted after `present_return_options`). |
| `decision` | `{ "outcome": "...", "item": "...|null", "amount": "...|null", "reason": "..." }` | A terminal/binding decision (`APPROVE`, `DENY`, `ESCALATE`). |
| `done` | `{}` | The turn is complete. |
| `error` | `{ "code": "...", "message": "..." }` | A safe, customer-facing error (e.g. `llm_unavailable`, `internal_error`). Never a raw 500 mid-stream. |

Trace persistence is independent of these events — see [`architecture.md`](architecture.md).

## Admin (read-only)

### `GET /api/admin/conversations`

Query params: `status` (optional), `limit` (1–200, default 50), `offset` (≥0). Returns conversations with status and last decision.

### `GET /api/admin/conversations/{conversation_id}/trace`

The full `agent_steps` timeline for one conversation — model text, each tool call (name + input), each tool result (output), per-step latency, and the binding decision with `policy_refs`. **404** if the conversation does not exist.

### `GET /api/admin/refunds`

Query params: `status` (optional), `limit` (1–200, default 50), `offset` (≥0). The refund audit log.

### `GET /api/admin/metrics`

Approval / denial / escalation counts.

## Health

### `GET /api/health`

```json
{ "status": "ok | degraded", "db": "ok | down", "llm_configured": true }
```

Returns **200** when the DB is reachable, **503** when it is down (so the compose healthcheck gates dependents). `llm_configured` reflects whether the selected provider has a usable key (`fake` is always configured).

## Error envelope

Every error response uses a uniform shape:

```json
{ "error": { "code": "string", "message": "string" } }
```

Validation errors → `422` / `validation_error`. Unexpected errors → `500` / `internal_error` (details are logged, never returned).

## Frontend client contract

The frontend's TypeScript client is generated from the backend's `/openapi.json` (`make gen-client`). The Pydantic schemas are the single source of truth. The only piece OpenAPI does not fully describe — the SSE event shapes above — is mirrored as a small hand-written TS type in the client. Regenerate after any backend schema change.
