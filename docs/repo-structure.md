# Repository & Code Structure

> Monorepo for the Refund Agent. Companion to `docs/design.md`.
> Layout = plain directory monorepo (no Nx/Turbo). Cross-language contract = backend OpenAPI → generated TS client.

---

## 1. Decisions behind this layout

- **Plain directory monorepo, no monorepo tool.** Two packages, two languages (Python + Node). Nx/Turborepo are JS-centric and add orchestration we don't need at this scale. A root `Makefile` + `docker-compose.yml` are the only "orchestrators," and they're language-neutral and obvious to reviewers.
- **`apps/` for runnable services, `infra/` for ops, `docs/` for design.** Clear top-level intent at a glance.
- **One source of truth for the API contract.** Pydantic schemas in the backend generate OpenAPI; the frontend generates its TypeScript client/types from that OpenAPI doc. No hand-maintained shared types package, so the two sides cannot drift.
- **Per-app tooling stays inside the app.** Python deps/config live in `apps/backend`; Node deps/config in `apps/frontend`. The root holds only cross-cutting things (compose, env example, Makefile, docs). Nothing forces a Python dev to install Node or vice-versa for their own slice.

---

## 2. Top-level tree

```
refund-agent/
├── apps/
│   ├── backend/                 # FastAPI + agent (Python)
│   └── frontend/                # React + Vite (TypeScript)
├── infra/
│   ├── docker/
│   │   ├── backend.Dockerfile
│   │   └── frontend.Dockerfile
│   └── nginx/
│       └── nginx.conf           # serves built SPA, proxies /api → backend
├── docs/
│   ├── design.md                # architecture (existing)
│   ├── repo-structure.md        # this file
│   └── challenge.md             # the assignment (existing)
├── scripts/
│   ├── gen-api-client.sh        # OpenAPI → frontend TS client
│   └── wait-for-db.sh           # optional startup helper
├── docker-compose.yml           # the single-command entrypoint
├── .env.example                 # documents every required var (API key, etc.)
├── .gitignore
├── .dockerignore
├── Makefile                     # DX shortcuts: up, seed, test, gen-client, lint
└── README.md                    # setup + agent-loop overview (deliverable)
```

Why these top-level files matter for the eval: `docker-compose.yml` + `.env.example` + `README.md` are the literal "single-command setup" + "documentation" deliverables. They sit at the root so a reviewer finds them in three seconds.

---

## 3. Backend — `apps/backend/`

Mirrors the layering contract in `design.md §5.1` (routers → agent → tools → services → repositories). The dependency rule is one-directional: outer layers import inner, never the reverse.

```
apps/backend/
├── app/
│   ├── main.py                  # app factory: CORS, router mount, lifespan (migrate+seed)
│   │
│   ├── core/
│   │   ├── config.py            # pydantic-settings: env vars (LLM_PROVIDER, keys, SEED_ENABLED, DB_URL, MAX_AGENT_ITERATIONS)
│   │   ├── logging.py           # structured logging setup
│   │   ├── llm/
│   │   │   ├── base.py          # LLMClient interface (chat, stream, tool schema fmt)
│   │   │   ├── anthropic.py     # default impl
│   │   │   └── openai.py        # alt impl, selected by LLM_PROVIDER
│   │   └── prompts/
│   │       └── system_prompt.py # hardened system prompt (single source)
│   │
│   ├── api/                     # HTTP only — parse, delegate, return
│   │   ├── deps.py              # shared dependencies (db session, conversation loader)
│   │   └── routers/
│   │       ├── chat.py          # POST /api/chat (SSE stream)
│   │       ├── conversations.py # create / get history
│   │       ├── admin.py         # conversations list, trace, refunds, metrics
│   │       └── health.py        # /api/health
│   │
│   ├── agent/                   # orchestration — knows nothing about SQL
│   │   ├── loop.py              # the tool-calling loop + SSE event emission
│   │   ├── registry.py          # maps tool name → callable + JSON schema
│   │   └── events.py            # SSE event types (token, tool_call, tool_result, decision, done)
│   │
│   ├── tools/                   # framework-agnostic adapters; ENFORCE policy here
│   │   ├── identity.py          # verify_identity
│   │   ├── lookup.py            # lookup_orders, get_order_details, get_policy
│   │   ├── eligibility.py       # check_refund_eligibility (read-only)
│   │   ├── refund.py            # process_refund (re-validates, then writes)
│   │   └── escalate.py          # escalate_to_human
│   │
│   ├── services/                # business logic; no HTTP, no LLM
│   │   ├── rule_engine.py       # the deterministic decision() function (binding)
│   │   ├── refund_service.py
│   │   ├── customer_service.py
│   │   └── policy_service.py
│   │
│   ├── repositories/            # data access only; no business rules
│   │   ├── customers.py
│   │   ├── orders.py
│   │   ├── refunds.py
│   │   ├── conversations.py
│   │   ├── messages.py
│   │   ├── agent_steps.py
│   │   └── policy.py
│   │
│   ├── models/                  # SQLAlchemy ORM (one file per table group)
│   │   ├── base.py
│   │   ├── crm.py               # customers, orders, order_items
│   │   ├── refunds.py
│   │   ├── conversation.py      # conversations, messages, agent_steps
│   │   └── policy.py            # policy_documents, policy_rules
│   │
│   ├── schemas/                 # Pydantic — request/response + tool IO (drives OpenAPI)
│   │   ├── chat.py
│   │   ├── admin.py
│   │   └── tools.py             # input/output schema per tool
│   │
│   ├── db/
│   │   ├── session.py           # engine + session factory
│   │   └── migrations/          # Alembic
│   │
│   └── seed/
│       ├── seed.py              # idempotent; gated by SEED_ENABLED
│       ├── fixtures.py          # the ~15 customers + adversarial cases
│       └── policy_source.py     # constants → both policy_documents text AND policy_rules
│
├── tests/
│   ├── unit/
│   │   ├── test_rule_engine.py  # pure-function tests for every decision branch
│   │   └── test_tools.py        # tools reject bad input / enforce policy
│   ├── integration/
│   │   └── test_chat_flow.py    # end-to-end turn against a test DB
│   └── adversarial/
│       └── test_resilience.py   # F9 proof: injection, final-sale, >$500, ownership, double-refund
│
├── pyproject.toml               # deps + ruff/black/mypy config
├── alembic.ini
└── .env.example                 # backend-specific vars (symlinked/duplicated subset of root)
```

### Module responsibilities (the parts that aren't obvious)

- `agent/loop.py` is the only place the LLM is driven. It calls `registry` to dispatch tools, writes each step via `repositories/agent_steps.py`, and emits SSE events via `events.py`. **Trace writes happen here, independent of whether the SSE socket is alive** (design.md §5.3).
- `tools/refund.py` and `tools/eligibility.py` both call `services/rule_engine.py`. The rule engine is the single binding authority; tools never re-implement rules.
- `seed/policy_source.py` is the anti-drift mechanism: the prose policy and the structured `policy_rules` are generated from the same constants, so the text the LLM reads and the rules code enforces can't disagree.
- `core/prompts/system_prompt.py` keeps the hardened prompt in one auditable place rather than inlined in the loop.

---

## 4. Frontend — `apps/frontend/`

```
apps/frontend/
├── src/
│   ├── main.tsx                 # entry
│   ├── App.tsx                  # router: /chat, /admin
│   │
│   ├── api/
│   │   ├── generated/           # TS client generated from backend OpenAPI (git-ignored or committed)
│   │   └── client.ts            # thin wrapper: base URL, SSE helper, error handling
│   │
│   ├── features/
│   │   ├── chat/
│   │   │   ├── ChatPage.tsx
│   │   │   ├── ChatWindow.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── DecisionBadge.tsx
│   │   │   ├── Composer.tsx
│   │   │   └── useChatStream.ts # consumes SSE, appends tokens, sets decision
│   │   └── admin/
│   │       ├── AdminPage.tsx
│   │       ├── ConversationList.tsx
│   │       ├── TraceTimeline.tsx
│   │       ├── StepCard.tsx     # renders one agent_step (tool call/result + latency)
│   │       ├── RefundTable.tsx
│   │       └── MetricsBar.tsx   # (S2)
│   │
│   ├── components/              # shared dumb UI (Button, Badge, Table, Spinner)
│   ├── hooks/                   # cross-feature hooks (useApi via React Query)
│   ├── lib/                     # formatters, constants
│   └── styles/                  # Tailwind entry
│
├── public/
├── tests/                       # component tests (Vitest + Testing Library)
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── .env.example                 # VITE_API_BASE_URL
```

### Frontend conventions

- **Feature-folder structure**, not type-folder. Everything for chat lives under `features/chat`; everything for the admin trace under `features/admin`. Shared primitives go to `components/`. This keeps the two screens independently legible.
- `api/generated/` is produced by `scripts/gen-api-client.sh` from the backend's `/openapi.json`. Hand-written `client.ts` wraps it with the SSE helper (the generator won't handle streaming for us) and error normalization.
- `useChatStream.ts` is the streaming brain on the client: opens the SSE connection, appends `token` deltas, surfaces `tool_call`/`tool_result` as live status, flips the `DecisionBadge` on the terminal `decision` event.

---

## 5. The API contract flow (how the two apps stay in sync)

```
Pydantic schemas (apps/backend/app/schemas/*)
        │  FastAPI emits
        ▼
   /openapi.json  ──── scripts/gen-api-client.sh ────►  apps/frontend/src/api/generated/
```

Run `make gen-client` after changing any backend schema. One source of truth (Pydantic); the frontend types are derived, never authored. SSE event shapes (`agent/events.py`) are the one piece OpenAPI doesn't fully describe — those are mirrored as a small hand-written TS type in `client.ts`, documented as the single exception.

---

## 6. Root developer-experience files

**Makefile targets** (the DX surface):

```
make up            # docker-compose up --build
make down          # docker-compose down -v
make seed          # re-run seeding against running DB
make gen-client    # regenerate frontend API client from backend OpenAPI
make test          # backend (pytest) + frontend (vitest)
make test-adv      # adversarial resilience suite only (F9 proof)
make lint          # ruff/mypy + eslint/tsc
```

**`.env.example`** (root, consumed by compose) documents every variable:

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
SEED_ENABLED=true
MAX_AGENT_ITERATIONS=8
POSTGRES_USER=refund
POSTGRES_PASSWORD=refund
POSTGRES_DB=refund
```

---

## 7. Conventions summary

- **Naming**: Python `snake_case` modules; React components `PascalCase.tsx`; hooks `useX.ts`.
- **Dependency direction (backend)**: `api → agent → tools → services → repositories → models`. A lint check (import-linter) can enforce this so the separation isn't just aspirational.
- **No business logic in routers; no SQL in services; no rules outside `rule_engine.py`.**
- **Tests live beside the app they test**, with the adversarial suite isolated so `make test-adv` can run it standalone as the resilience demonstration.

---

## 8. Note / open question

`src/api/generated/` — commit it or git-ignore + generate on build? Committing makes the repo work without running the generator (safer for reviewers cloning fresh); git-ignoring keeps the tree clean but adds a build step. **Recommendation: commit it**, regenerate via `make gen-client`, so `docker-compose up` never depends on a codegen step succeeding. Your call.
