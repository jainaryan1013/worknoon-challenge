"""present_return_options — Return Selector discovery (docs/components/03 §3.7b).

Read-only. Lists returnable items (remaining > 0) with a UI eligibility hint.
The binding check still happens in process_refund at confirm time.
"""

from __future__ import annotations

from pydantic import ValidationError

from app.schemas.tools import OrderRefInput, ToolResult
from app.services import customer_service
from app.services.errors import ServiceError
from app.tools.common import PolicyLoadError, load_rules, require_identity
from app.tools.context import ToolContext


def present_return_options(ctx: ToolContext, args: dict) -> ToolResult:
    gate = require_identity(ctx)
    if gate is not None:
        return gate
    try:
        data = OrderRefInput.model_validate(args)
    except ValidationError:
        return ToolResult.fail("invalid_input", "Please provide an order number.")

    try:
        rules = load_rules(ctx)
    except PolicyLoadError:
        return ToolResult.fail("policy_unavailable", "Returns are temporarily unavailable.")

    try:
        options = customer_service.present_return_options(
            ctx.db, data.order_number, ctx.verified_customer_id, rules
        )
    except ServiceError as exc:
        return ToolResult.fail(exc.code, exc.message)
    return ToolResult.success(options)
