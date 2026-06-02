"""The tool-calling agent loop (docs/components/04 §3-4).

Drives the turn: ask the model, dispatch chosen tools, feed results back, stream
SSE events, and persist a complete trace. Two invariants matter here:

- The loop has NO authority to approve a refund. It only calls tools; the tools
  enforce. Prompt hardening is defense-in-depth, not the boundary.
- Trace persistence is decoupled from the socket: every messages/agent_steps row
  is written as the loop executes, independent of whether the SSE emit succeeds.
  If the client disconnects, the loop runs to completion server-side anyway.

Disconnect handling note: emission uses *direct* `yield` guarded by try/except
GeneratorExit. We deliberately avoid `yield from` here — delegating a yield
re-raises GeneratorExit into this generator (PEP 380), which would abort the
turn early. Catching it at the direct yield lets us flip to "don't emit" and
keep running to completion.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

from loguru import logger

from app.agent import events, registry
from app.core.config import get_settings
from app.core.llm.base import LLMError, TextDelta, ToolCall, TurnEnd
from app.core.prompts.system_prompt import SYSTEM_PROMPT
from app.repositories import agent_steps as agent_steps_repo
from app.repositories import conversations as conversations_repo
from app.repositories import messages as messages_repo
from app.tools.context import ToolContext

_TERMINAL = ("APPROVE", "DENY", "ESCALATE")

# Per-conversation turn locks: serialize turns so step_no stays monotonic.
_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


def _lock_for(conversation_id: uuid.UUID) -> threading.RLock:
    with _locks_guard:
        return _locks.setdefault(str(conversation_id), threading.RLock())


def run_turn(
    db,
    llm,
    conversation_id: uuid.UUID,
    user_text: str,
    *,
    selection: list[dict] | None = None,
    now: datetime | None = None,
    max_iterations: int | None = None,
    history_limit: int | None = None,
) -> Iterator[events.SSEEvent]:
    settings = get_settings()
    max_iterations = max_iterations or settings.max_agent_iterations
    history_limit = settings.history_limit if history_limit is None else history_limit
    now = now or datetime.now(timezone.utc)
    state = {"alive": True}

    lock = _lock_for(conversation_id)
    lock.acquire()
    try:
        conv = conversations_repo.get(db, conversation_id)
        verified = conv.customer_id if conv is not None else None

        messages_repo.add(db, conversation_id, "user", user_text)

        provider_msgs: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in messages_repo.history(db, conversation_id, history_limit):
            provider_msgs.append({"role": m.role, "content": m.content})
        if selection:
            provider_msgs.append(
                {
                    "role": "user",
                    "content": "[selection] The customer selected these items to return: "
                    + json.dumps(selection),
                }
            )

        ctx = ToolContext(
            db=db, conversation_id=conversation_id, verified_customer_id=verified
        )
        step = agent_steps_repo.next_step_no(db, conversation_id)

        for _iteration in range(1, max_iterations + 1):
            assistant_text = ""
            tool_calls: list[ToolCall] = []
            try:
                for ev in llm.stream_turn(provider_msgs, registry.tool_schemas()):
                    if isinstance(ev, TextDelta):
                        assistant_text += ev.text
                        if state["alive"]:
                            try:
                                yield events.token(ev.text)
                            except GeneratorExit:
                                state["alive"] = False
                    elif isinstance(ev, ToolCall):
                        tool_calls.append(ev)
                    elif isinstance(ev, TurnEnd):
                        break
            except LLMError as exc:
                # Surface the real provider error server-side (e.g. a 400 from a
                # bad model param) at ERROR; the customer sees a safe message.
                logger.error("LLM call failed for conversation {}: {}", conversation_id, exc)
                if state["alive"]:
                    try:
                        yield events.error(
                            "llm_unavailable",
                            "The assistant is temporarily unavailable. Please try again shortly.",
                        )
                    except GeneratorExit:
                        state["alive"] = False
                if state["alive"]:
                    try:
                        yield events.done()
                    except GeneratorExit:
                        state["alive"] = False
                return

            asst = messages_repo.add(db, conversation_id, "assistant", assistant_text)
            agent_steps_repo.add(
                db,
                conversation_id=conversation_id,
                step_no=step,
                type="model_text",
                message_id=asst.id,
            )
            step += 1

            if not tool_calls:
                if state["alive"]:
                    try:
                        yield events.done()
                    except GeneratorExit:
                        state["alive"] = False
                return

            provider_msgs.append(
                {
                    "role": "assistant",
                    "content": assistant_text,
                    "tool_calls": [
                        {"call_id": c.call_id, "name": c.name, "args": c.args}
                        for c in tool_calls
                    ],
                }
            )

            for call in tool_calls:
                if state["alive"]:
                    try:
                        yield events.tool_call(
                            call.name, events.friendly_summary(call.name, call.args)
                        )
                    except GeneratorExit:
                        state["alive"] = False

                t0 = time.perf_counter()
                result = registry.dispatch(call.name, call.args, ctx)
                latency = int((time.perf_counter() - t0) * 1000)

                agent_steps_repo.add(
                    db,
                    conversation_id=conversation_id,
                    step_no=step,
                    type="tool_call",
                    tool_name=call.name,
                    tool_input=call.args,
                    latency_ms=latency,
                )
                step += 1

                payload = result.model_dump()
                agent_steps_repo.add(
                    db,
                    conversation_id=conversation_id,
                    step_no=step,
                    type="tool_result",
                    tool_name=call.name,
                    tool_output=payload,
                )
                step += 1

                status = "ok" if result.ok else (result.error.code if result.error else "error")
                if state["alive"]:
                    try:
                        yield events.tool_result(call.name, status)
                    except GeneratorExit:
                        state["alive"] = False

                if call.name == "present_return_options" and result.ok and state["alive"]:
                    try:
                        yield events.return_selector(result.data)
                    except GeneratorExit:
                        state["alive"] = False

                step, decision_ev = _record_decision(db, conversation_id, step, call, result)
                if decision_ev is not None and state["alive"]:
                    try:
                        yield decision_ev
                    except GeneratorExit:
                        state["alive"] = False

                provider_msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.call_id,
                        "content": json.dumps(payload),
                    }
                )

        # Iteration cap reached without a final answer — fail closed.
        agent_steps_repo.add(
            db,
            conversation_id=conversation_id,
            step_no=step,
            type="decision",
            tool_output={"outcome": "ESCALATE", "reason": "iteration_cap"},
        )
        step += 1
        if conv is not None:
            conversations_repo.set_status(db, conv, "escalated")
        if state["alive"]:
            try:
                yield events.decision(
                    "ESCALATE",
                    None,
                    None,
                    "We couldn't resolve this automatically and have routed it to a specialist.",
                )
            except GeneratorExit:
                state["alive"] = False
        if state["alive"]:
            try:
                yield events.done()
            except GeneratorExit:
                state["alive"] = False
    finally:
        lock.release()


def _record_decision(db, conversation_id, step, call, result):
    """Persist a decision step for binding outcomes (process_refund terminal
    verdicts, manual escalations) and return (next_step, event_or_None). Does
    not yield — emission is the caller's job, so disconnect can't skip the write.
    """
    if call.name == "process_refund" and result.ok and isinstance(result.data, dict):
        data = result.data
        if data.get("outcome") in _TERMINAL:
            agent_steps_repo.add(
                db,
                conversation_id=conversation_id,
                step_no=step,
                type="decision",
                tool_name=call.name,
                tool_output=data,
            )
            return step + 1, events.decision(
                data["outcome"],
                call.args.get("line_ref"),
                data.get("amount"),
                data.get("message", ""),
            )
    elif call.name == "escalate_to_human" and result.ok:
        agent_steps_repo.add(
            db,
            conversation_id=conversation_id,
            step_no=step,
            type="decision",
            tool_name=call.name,
            tool_output=result.data,
        )
        return step + 1, events.decision(
            "ESCALATE", call.args.get("line_ref"), None, "Escalated to a specialist."
        )
    return step, None
