# Configuration

All variables are read from the environment / `.env` by `app/core/config.py` (pydantic-settings). The rest of the app never reads `os.environ` directly. Copy `.env.example` to `.env` before running.

> **Note:** `docker-compose` `env_file` does **not** strip inline comments. Keep every comment on its own line — `KEY=val # x` would set `KEY` to the literal `"val # x"`.

## Variables

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `openai` | Provider: `openai`, `anthropic`, or `fake`. `fake` is a deterministic, key-free test/demo provider. |
| `OPENAI_API_KEY` | _(empty)_ | Required when `LLM_PROVIDER=openai`. |
| `ANTHROPIC_API_KEY` | _(empty)_ | Required when `LLM_PROVIDER=anthropic`. |
| `LLM_MODEL` | _(empty)_ | Optional model override; blank uses a sensible per-provider default. |
| `LLM_TEMPERATURE` | `0` | Sampling temperature. `0` for deterministic decisioning. |
| `LLM_MAX_TOKENS` | `2048` | Max output tokens. Reasoning models bill hidden reasoning against this cap, so keep headroom for a visible answer. |
| `MAX_AGENT_ITERATIONS` | `8` | Tool-loop iteration cap. Exhausting it fails closed (escalates), never approves. |
| `HISTORY_LIMIT` | `-1` | Prior messages fed per turn. `-1` = unlimited (demo default). |
| `SEED_ENABLED` | `true` | Run idempotent seeding at startup. Set `false` to boot against an already-populated DB. |
| `FRONTEND_ORIGIN` | `http://localhost:8080` | The single CORS-allowed origin for the API. |
| `DATABASE_URL` | `postgresql+psycopg://refund:refund@db:5432/refund` | Sync psycopg v3 DSN. Set by compose from the `POSTGRES_*` vars; the test runner points it at `db-test`. |
| `POSTGRES_USER` | `refund` | Postgres user (consumed by the `db` service and the `DATABASE_URL`). |
| `POSTGRES_PASSWORD` | `refund` | Postgres password. |
| `POSTGRES_DB` | `refund` | Postgres database name. |

## Key behavior

- **No key required to boot.** The app starts regardless. `GET /api/health` reports `llm_configured`, and the first chat returns a clear, safe error if the selected provider has no key. The `fake` provider always reports configured.
- **Provider selection** is a single `LLMClient` interface with `openai`, `anthropic`, and `fake` implementations, chosen by `LLM_PROVIDER`.
- **Determinism for decisions** comes from the rule engine, not the model — temperature only affects phrasing.

Authoritative source: `app/core/config.py` and `.env.example`. See `docs/components/07-infra.md` §6 for infra-level detail.
