"""check_refund_eligibility — read-only preview (docs/components/03 §3.5).

Shares decision() with process_refund, so the preview matches the action
(modulo concurrent changes, which process_refund resolves under lock).
"""

from __future__ import annotations

from pydantic import ValidationError

from app.schemas.tools import RefundInput, ToolResult
from app.services import refund_service
from app.services.errors import ServiceError
from app.tools.common import PolicyLoadError, degraded_escalation, load_rules, require_identity
from app.tools.context import ToolContext


def check_refund_eligibility(ctx: ToolContext, args: dict) -> ToolResult:
    gate = require_identity(ctx)
    if gate is not None:
        return gate
    try:
        data = RefundInput.model_validate(args)
    except ValidationError:
        return ToolResult.fail("invalid_input", "Provide order_number, line_ref, and quantity.")

    try:
        rules = load_rules(ctx)
    except PolicyLoadError:
        return ToolResult.success(degraded_escalation(data.quantity).to_public_dict())

    try:
        verdict = refund_service.check_eligibility(
            ctx.db,
            order_number=data.order_number,
            line_ref=data.line_ref,
            quantity=data.quantity,
            verified_customer_id=ctx.verified_customer_id,
            rules=rules,
        )
    except ServiceError as exc:
        return ToolResult.fail(exc.code, exc.message)
    return ToolResult.success(verdict.to_public_dict())
