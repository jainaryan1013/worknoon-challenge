"""escalate_to_human — idempotent record + inform (docs/components/03 §3.7).

v1 records the escalation and tells the customer; no live paging.
"""

from __future__ import annotations

from pydantic import ValidationError

from app.schemas.tools import EscalateInput, ToolResult
from app.services import refund_service
from app.services.errors import ServiceError
from app.tools.common import PolicyLoadError, load_rules, require_identity
from app.tools.context import ToolContext


def escalate_to_human(ctx: ToolContext, args: dict) -> ToolResult:
    gate = require_identity(ctx)
    if gate is not None:
        return gate
    try:
        data = EscalateInput.model_validate(args)
    except ValidationError:
        return ToolResult.fail("invalid_input", "Please provide an order number and a summary.")

    try:
        rules = load_rules(ctx)
    except PolicyLoadError:
        rules = None  # escalation doesn't need rules to record a hand-off

    try:
        result = refund_service.escalate(
            ctx.db,
            order_number=data.order_number,
            line_ref=data.line_ref,
            summary=data.summary,
            verified_customer_id=ctx.verified_customer_id,
            conversation_id=ctx.conversation_id,
            rules=rules,
        )
    except ServiceError as exc:
        return ToolResult.fail(exc.code, exc.message)
    return ToolResult.success(result)
