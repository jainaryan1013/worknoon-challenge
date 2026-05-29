"""Read tools: lookup_orders, get_order_details, get_policy
(docs/components/03 §3.2-3.4).
"""

from __future__ import annotations

from pydantic import ValidationError

from app.schemas.tools import OrderRefInput, ToolResult
from app.services import customer_service, policy_service
from app.services.errors import ServiceError
from app.tools.common import require_identity
from app.tools.context import ToolContext


def lookup_orders(ctx: ToolContext, args: dict) -> ToolResult:
    gate = require_identity(ctx)
    if gate is not None:
        return gate
    orders = customer_service.lookup_orders(ctx.db, ctx.verified_customer_id)
    return ToolResult.success({"orders": orders})


def get_order_details(ctx: ToolContext, args: dict) -> ToolResult:
    gate = require_identity(ctx)
    if gate is not None:
        return gate
    try:
        data = OrderRefInput.model_validate(args)
    except ValidationError:
        return ToolResult.fail("invalid_input", "Please provide an order number.")
    try:
        details = customer_service.get_order_details(
            ctx.db, data.order_number, ctx.verified_customer_id
        )
    except ServiceError as exc:
        return ToolResult.fail(exc.code, exc.message)
    return ToolResult.success(details)


def get_policy(ctx: ToolContext, args: dict) -> ToolResult:
    # No identity required — policy is not customer data.
    record = policy_service.get_policy_document_record(ctx.db)
    return ToolResult.success(record)
