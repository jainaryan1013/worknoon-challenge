"""verify_identity tool — establishes identity and binds conversation.customer_id
(docs/components/03 §3.1). The only tool that may run unverified.
"""

from __future__ import annotations

from pydantic import ValidationError

from app.repositories import conversations as conversations_repo
from app.schemas.tools import ToolResult, VerifyIdentityInput
from app.services import customer_service
from app.tools.context import ToolContext

_GENERIC_FAIL = "We couldn't verify those details. Please check the order number and email."


def verify_identity(ctx: ToolContext, args: dict) -> ToolResult:
    try:
        data = VerifyIdentityInput.model_validate(args)
    except ValidationError:
        return ToolResult.fail("invalid_input", "Please provide an order number and email.")

    conv = (
        conversations_repo.get(ctx.db, ctx.conversation_id)
        if ctx.conversation_id is not None
        else None
    )
    if conv is None:
        return ToolResult.fail("verification_failed", _GENERIC_FAIL)

    customer = customer_service.verify_identity(ctx.db, conv, data.order_number, data.email)
    if customer is None:
        # Generic on every failure path — never reveal whether order/email existed.
        return ToolResult.fail("verification_failed", _GENERIC_FAIL)

    ctx.verified_customer_id = customer.id
    return ToolResult.success({"verified": True, "customer_name": customer.name})
