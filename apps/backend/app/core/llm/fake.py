"""Deterministic fake LLM provider (LLM_PROVIDER=fake).

TEST/DEMO SCAFFOLDING — not a real model. It drives the canonical refund flows
by inspecting the message list and emitting tool calls, so the *entire* stack
runs end-to-end (real tools, rule engine, locking, persistence) with a
reproducible "brain". The actual agent quality is validated separately with a
real provider + API key.

It deliberately routes every decision through the real tools, so authorization
is still enforced server-side exactly as in production.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator

from app.core.llm.base import LLMEvent, TextDelta, ToolCall, TurnEnd

_ORDER_RE = re.compile(r"ORD-\d+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


class FakeLLMClient:
    def format_tools(self, tool_schemas: list[dict]) -> list[dict]:
        return tool_schemas

    # --- message inspection helpers ----------------------------------------

    @staticmethod
    def _tool_history(messages: list[dict]) -> list[tuple[str, dict]]:
        names: dict[str, str] = {}
        out: list[tuple[str, dict]] = []
        for m in messages:
            if m.get("role") == "assistant" and m.get("tool_calls"):
                for c in m["tool_calls"]:
                    names[c["call_id"]] = c["name"]
            elif m.get("role") == "tool":
                try:
                    payload = json.loads(m.get("content") or "{}")
                except json.JSONDecodeError:
                    payload = {}
                out.append((names.get(m.get("tool_call_id", ""), ""), payload))
        return out

    @staticmethod
    def _last_user_text(messages: list[dict]) -> str:
        for m in reversed(messages):
            content = m.get("content") or ""
            if m.get("role") == "user" and not content.startswith("[selection]"):
                return content
        return ""

    @staticmethod
    def _selection(messages: list[dict]) -> list[dict] | None:
        for m in reversed(messages):
            content = m.get("content") or ""
            if m.get("role") == "user" and content.startswith("[selection]"):
                try:
                    return json.loads(content.split("return: ", 1)[1])
                except (IndexError, json.JSONDecodeError):
                    return None
        return None

    @staticmethod
    def _order_number(text: str, messages: list[dict]) -> str | None:
        match = _ORDER_RE.search(text)
        if match:
            return match.group(0)
        for m in messages:
            if m.get("role") == "user":
                found = _ORDER_RE.search(m.get("content") or "")
                if found:
                    return found.group(0)
        return None

    @staticmethod
    def _match_line_ref(history: list[tuple[str, dict]], text: str) -> str | None:
        lowered = text.lower()
        for name, payload in history:
            if name in ("get_order_details", "present_return_options") and payload.get("ok"):
                items = (payload.get("data") or {}).get("items", [])
                for item in items:
                    label = item.get("line_ref") or item.get("product_name") or ""
                    if label and label.lower() in lowered:
                        return label
                if items:  # fall back to the first item so the demo still flows
                    return items[0].get("line_ref")
        return None

    # --- the "brain" -------------------------------------------------------

    def stream_turn(self, messages: list[dict], tools: list[dict]) -> Iterator[LLMEvent]:
        history = self._tool_history(messages)
        done = [n for n, _ in history]
        text = self._last_user_text(messages)
        order = self._order_number(text, messages)
        selection = self._selection(messages)

        # 1. Confirmed Return Selector → one process_refund per selected item.
        if selection:
            processed = done.count("process_refund")
            if processed < len(selection):
                for i, sel in enumerate(selection[processed:], start=processed):
                    yield ToolCall(
                        "process_refund",
                        {
                            "order_number": order,
                            "line_ref": sel.get("line_ref"),
                            "quantity": sel.get("quantity", 1),
                        },
                        f"fake-refund-{i}",
                    )
                yield TurnEnd("tool_calls")
                return
            yield TextDelta("All set — I've processed your selected returns.")
            yield TurnEnd("stop")
            return

        # 2. Verify when the latest message carries credentials.
        email = _EMAIL_RE.search(text)
        if order and email and "verify_identity" not in done:
            yield ToolCall(
                "verify_identity",
                {"order_number": order, "email": email.group(0)},
                "fake-verify",
            )
            yield TurnEnd("tool_calls")
            return

        lowered = text.lower()

        # 3. Return intent → present options for the Return Selector.
        if "return" in lowered and "refund" not in lowered:
            if not order:
                yield TextDelta("Sure — what's your order number?")
                yield TurnEnd("stop")
                return
            if "present_return_options" not in done:
                yield ToolCall("present_return_options", {"order_number": order}, "fake-return")
                yield TurnEnd("tool_calls")
                return
            yield TextDelta("Here are your returnable items — pick what you'd like to return.")
            yield TurnEnd("stop")
            return

        # 4. Direct refund intent → details, then process per matched item.
        if "refund" in lowered:
            if "process_refund" in done:
                yield TextDelta("All done — I've handled your refund request. Anything else?")
                yield TurnEnd("stop")
                return
            if not order:
                yield TextDelta("Happy to help — what's your order number?")
                yield TurnEnd("stop")
                return
            if "get_order_details" not in done:
                yield ToolCall("get_order_details", {"order_number": order}, "fake-details")
                yield TurnEnd("tool_calls")
                return
            line_ref = self._match_line_ref(history, text)
            if line_ref:
                yield ToolCall(
                    "process_refund",
                    {"order_number": order, "line_ref": line_ref, "quantity": 1},
                    "fake-refund",
                )
                yield TurnEnd("tool_calls")
                return
            yield TextDelta("Which item would you like refunded?")
            yield TurnEnd("stop")
            return

        # 5. Fallback.
        if "verify_identity" not in done and not (order and email):
            yield TextDelta(
                "Hi! Share your order number and the email on the order and I can help with a refund or return."
            )
        else:
            yield TextDelta("How can I help with your order today?")
        yield TurnEnd("stop")
