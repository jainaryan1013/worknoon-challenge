# Refund Agent — Documentation

Complete documentation for the Refund Agent. Start with the root [`../README.md`](../README.md) for setup; everything else is here.

## Handbook (start here)

| Doc | What's in it |
|---|---|
| [overview.md](overview.md) | What the system is, the "LLM orchestrates, code authorizes" principle, feature summary. |
| [quickstart.md](quickstart.md) | Prerequisites, one-command run, URLs, common commands. |
| [architecture.md](architecture.md) | Layering contract, request lifecycle, streaming + trace decoupling, framework choice. |
| [configuration.md](configuration.md) | Every environment variable, default, and behavior. |
| [data-model.md](data-model.md) | All tables, the quantity invariant, policy-stored-twice, seed fixtures. |
| [api-reference.md](api-reference.md) | Every endpoint, the SSE event vocabulary, the error envelope. |
| [agent-and-tools.md](agent-and-tools.md) | The agent loop, all 8 tools, the guardrails. |
| [rule-engine.md](rule-engine.md) | The 8-step decision precedence, outcomes, reason codes, policy constants. |
| [testing.md](testing.md) | Every `make` target, the test stacks, the adversarial suite. |
| [known-gaps.md](known-gaps.md) | Non-goals, in-scope clarifications, stretch items. |

## Deep design specs

The authoritative, design-stage specifications. Where a handbook page summarizes, these are the source of truth on any discrepancy.

| Doc | Scope |
|---|---|
| [design.md](design.md) | Full application design — feature matrix, architecture, every component. |
| [repo-structure.md](repo-structure.md) | Monorepo layout, module responsibilities, the API-contract flow. |
| [Challenge.md](Challenge.md) | The original assignment. |
| [components/01-database.md](components/01-database.md) | Database schema, constraints, fixture matrix. |
| [components/02-policy-rule-engine.md](components/02-policy-rule-engine.md) | The deterministic decision authority. |
| [components/03-tools-layer.md](components/03-tools-layer.md) | Tool boundary and contracts. |
| [components/04-agent-loop-llm-client.md](components/04-agent-loop-llm-client.md) | Agent loop, LLM client, system prompt, SSE. |
| [components/05-backend-api.md](components/05-backend-api.md) | API surface and request handling. |
| [components/06-frontend.md](components/06-frontend.md) | React SPA — chat and admin. |
| [components/07-infra.md](components/07-infra.md) | Docker, compose, env vars. |
| [components/08-adversarial-eval-suite.md](components/08-adversarial-eval-suite.md) | The resilience proof. |

## A note on accuracy

The handbook pages were verified against the implementation. Where the deep specs are design-stage and have drifted (for example, the spec lists 7 tools — the code has 8, including `present_return_options`), the handbook reflects the running code.
