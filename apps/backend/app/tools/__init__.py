"""Tool registry: name -> (callable, input schema).

The agent loop (#4) builds the LLM-facing JSON tool schemas from the input
models and dispatches calls by name. Every callable has the signature
`fn(ctx: ToolContext, args: dict) -> ToolResult`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel

from app.schemas.tools import (
    EmptyInput,
    EscalateInput,
    OrderRefInput,
    RefundInput,
    ToolResult,
    VerifyIdentityInput,
)
from app.tools.context import ToolContext
from app.tools.eligibility import check_refund_eligibility
from app.tools.escalate import escalate_to_human
from app.tools.identity import verify_identity
from app.tools.lookup import get_order_details, get_policy, lookup_orders
from app.tools.refund import process_refund
from app.tools.return_options import present_return_options


@dataclass(frozen=True)
class ToolSpec:
    name: str
    fn: Callable[[ToolContext, dict], ToolResult]
    input_model: type[BaseModel]
    description: str


REGISTRY: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in [
        ToolSpec("verify_identity", verify_identity, VerifyIdentityInput,
                 "Verify the customer's identity using their order number and email."),
        ToolSpec("lookup_orders", lookup_orders, EmptyInput,
                 "List the verified customer's orders."),
        ToolSpec("get_order_details", get_order_details, OrderRefInput,
                 "Get per-item detail for one of the customer's orders."),
        ToolSpec("get_policy", get_policy, EmptyInput,
                 "Retrieve the refund policy text to reason with and cite."),
        ToolSpec("check_refund_eligibility", check_refund_eligibility, RefundInput,
                 "Preview the refund outcome for N units of one item (no changes)."),
        ToolSpec("process_refund", process_refund, RefundInput,
                 "Make a binding refund decision for N units of one item and record it."),
        ToolSpec("present_return_options", present_return_options, OrderRefInput,
                 "List returnable items on an order with eligibility hints."),
        ToolSpec("escalate_to_human", escalate_to_human, EscalateInput,
                 "Hand a request off to a human specialist."),
    ]
}

__all__ = ["REGISTRY", "ToolSpec", "ToolContext"]
