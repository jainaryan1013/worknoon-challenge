"""Shared helpers for tool gates and fail-closed policy loading."""

from __future__ import annotations

from decimal import Decimal

from app.schemas.tools import ToolResult
from app.services import policy_service
from app.services.policy_service import PolicyLoadError
from app.services.rule_engine import Decision, Outcome, PolicyRules, ReasonCode
from app.tools.context import ToolContext


def require_identity(ctx: ToolContext) -> ToolResult | None:
    """Return an identity_required failure if the context isn't verified."""
    if ctx.verified_customer_id is None:
        return ToolResult.fail(
            "identity_required",
            "Please verify your identity first with your order number and email.",
        )
    return None


def load_rules(ctx: ToolContext) -> PolicyRules:
    """Load policy rules, raising PolicyLoadError on degraded policy (caller
    converts to ESCALATE, never APPROVE — §6 fail-closed)."""
    return policy_service.load_policy_rules(ctx.db)


def degraded_escalation(quantity: int) -> Decision:
    """Synthetic ESCALATE used when policy can't be loaded — route to a human."""
    return Decision(
        outcome=Outcome.ESCALATE,
        reason_code=ReasonCode.ESCALATED_OVER_THRESHOLD,
        message="This request needs review by a human specialist.",
        quantity=quantity,
        amount=Decimal("0.00"),
        policy_refs=["policy_unavailable"],
    )


__all__ = ["require_identity", "load_rules", "degraded_escalation", "PolicyLoadError"]
