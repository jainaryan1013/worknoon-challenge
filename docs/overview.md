# Overview

The Refund Agent is an AI customer-support agent that processes, denies, or escalates e-commerce refunds. A customer chats with the agent in natural language; an admin dashboard replays the agent's full reasoning trace, every tool call, and every binding decision.

It is a containerized monorepo: a **FastAPI** backend that hosts the agent, a **React + Vite** frontend, and **PostgreSQL** for data and observability. One command (`docker-compose up --build`) brings the whole stack up.

## Core principle

The single most important design decision:

> **The LLM orchestrates; deterministic code authorizes.**

The model decides *which tools to call and what to say*. It never has the final word on whether a refund is legal. Every state-changing tool re-validates the request against policy in pure Python (the rule engine in [`rule-engine.md`](rule-engine.md)) before doing anything. If a jailbroken model calls `process_refund` on a final-sale item or an over-threshold order, the tool itself rejects it.

This collapses the attack surface for "trick the AI into refunding" down to "trick deterministic code with hard-coded rules" — which is not reachable through chat. See [`agent-and-tools.md`](agent-and-tools.md) for the full guardrail list and [`architecture.md`](architecture.md) for how the layers enforce it.

## What it does

- **Customer chat** — conversational refund requests, streamed token-by-token over SSE.
- **Identity verification** — no order is actionable until `verify_identity` succeeds in the conversation.
- **CRM + policy lookup** — the agent reads orders, per-item detail, and the refund policy through tools.
- **Per-item, partial-quantity refunds** — each line item is refundable independently, in whole or partial quantity, on its own delivery date and return window.
- **Binding decisions** — APPROVE / DENY / ESCALATE / NEEDS_INFO, computed by the rule engine, never by the model.
- **Escalation** — requests whose projected per-order refund total would exceed the threshold are routed to a human.
- **Full reasoning trace** — every model turn, tool call, tool result, latency, and decision is persisted to `agent_steps` and surfaced in the admin dashboard.
- **Refund audit log** — who/what/why/when for every refund.
- **Prompt-injection resilience** — proven by a deterministic adversarial test suite (see [`testing.md`](testing.md)).

## Scope notes

Refunds are **per line item with partial-quantity support** — partial and multi-item refunds are in scope. The escalation threshold is evaluated on the **projected cumulative refund per order** (prior approved refunds on the order plus the current request), *before* the refund is confirmed.

For documented non-goals (no admin auth, no dispute-email processing, not production-hardened), see [`known-gaps.md`](known-gaps.md).
