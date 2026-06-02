"""SSE event vocabulary (docs/components/04 §5).

The customer-facing payloads carry NO internal ids or raw tool JSON — that split
is enforced here when building payloads, not left to the model. The full detail
lives in agent_steps for the admin trace.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class SSEEvent:
    type: str
    data: dict

    def format(self) -> str:
        """Wire format for an SSE stream."""
        return f"event: {self.type}\ndata: {json.dumps(self.data)}\n\n"


def token(text: str) -> SSEEvent:
    return SSEEvent("token", {"text": text})


def tool_call(tool: str, summary: str) -> SSEEvent:
    return SSEEvent("tool_call", {"tool": tool, "summary": summary})


def tool_result(tool: str, status: str) -> SSEEvent:
    return SSEEvent("tool_result", {"tool": tool, "status": status})


def return_selector(data: dict) -> SSEEvent:
    return SSEEvent("return_selector", data)


def decision(outcome: str, item: str | None, amount: str | None, reason: str) -> SSEEvent:
    return SSEEvent(
        "decision",
        {"outcome": outcome, "item": item, "amount": amount, "reason": reason},
    )


def done() -> SSEEvent:
    return SSEEvent("done", {})


def error(code: str, message: str) -> SSEEvent:
    return SSEEvent("error", {"code": code, "message": message})


_FRIENDLY = {
    "verify_identity": "Verifying your identity…",
    "lookup_orders": "Looking up your orders…",
    "get_order_details": "Loading your order…",
    "get_policy": "Reviewing the refund policy…",
    "check_refund_eligibility": "Checking eligibility…",
    "process_refund": "Processing your refund…",
    "present_return_options": "Preparing your return options…",
    "escalate_to_human": "Connecting you with a specialist…",
}


def friendly_summary(tool: str, args: dict) -> str:
    """A user-safe status line — uses only user-facing args (order_number,
    line_ref), never internal ids or full JSON."""
    base = _FRIENDLY.get(tool, "Working on it…")
    line_ref = args.get("line_ref")
    if tool in ("process_refund", "check_refund_eligibility") and line_ref:
        return f"{base[:-1]} for {line_ref}…"
    return base
