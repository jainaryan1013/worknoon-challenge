"""The binding refund decision authority (docs/components/02).

`decision()` is a PURE, deterministic function: no DB, no LLM, no I/O, no
side effects. Tools (spec #3) gather facts, call this, and act on the result;
they re-derive the verdict here and never trust the model's claim.

Evaluation precedence (§4) — first match wins:
    1. ownership      2. fully refunded   3. valid quantity   4. final sale
    5. not delivered  6. window           7. threshold        8. approve
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

_CENTS = Decimal("0.01")


class Outcome(str, enum.Enum):
    APPROVE = "APPROVE"
    DENY = "DENY"
    ESCALATE = "ESCALATE"
    NEEDS_INFO = "NEEDS_INFO"


class ReasonCode(str, enum.Enum):
    APPROVED = "APPROVED"
    DENIED_NOT_OWNER = "DENIED_NOT_OWNER"
    DENIED_FINAL_SALE = "DENIED_FINAL_SALE"
    DENIED_WINDOW_EXPIRED = "DENIED_WINDOW_EXPIRED"
    DENIED_FULLY_REFUNDED = "DENIED_FULLY_REFUNDED"
    ESCALATED_OVER_THRESHOLD = "ESCALATED_OVER_THRESHOLD"
    NEEDS_INFO_NOT_DELIVERED = "NEEDS_INFO_NOT_DELIVERED"
    NEEDS_INFO_INVALID_QUANTITY = "NEEDS_INFO_INVALID_QUANTITY"


@dataclass(frozen=True)
class ItemFacts:
    """The per-item facts the engine needs. Built by the tool from an ORM row;
    kept decoupled from SQLAlchemy so the engine stays trivially testable."""

    id: uuid.UUID
    order_id: uuid.UUID
    is_final_sale: bool
    return_window_days: int
    unit_price: Decimal
    quantity: int
    delivered_at: datetime | None


@dataclass(frozen=True)
class PolicyRules:
    """Typed view of policy_rules (loaded by policy_service)."""

    escalation_threshold_usd: Decimal
    default_return_window_days: int
    final_sale_refundable: bool
    dispute_email: str


@dataclass(frozen=True)
class Decision:
    outcome: Outcome
    reason_code: ReasonCode
    message: str
    quantity: int
    amount: Decimal
    policy_refs: list[str] = field(default_factory=list)
    dispute_email: str | None = None

    def to_public_dict(self) -> dict:
        """User-safe serialization for tool results / SSE (no internal ids)."""
        return {
            "outcome": self.outcome.value,
            "reason_code": self.reason_code.value,
            "message": self.message,
            "policy_refs": list(self.policy_refs),
            "quantity": self.quantity,
            "amount": str(self.amount),
            "dispute_email": self.dispute_email,
        }


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENTS)


def _days_between(start: datetime, end: datetime) -> int:
    """Whole days elapsed (floored). Window is inclusive: an item delivered
    exactly `return_window_days` ago is still eligible (`>` not `>=`)."""
    return (end - start).days


def decision(
    *,
    item: ItemFacts,
    requested_quantity: int,
    already_refunded_qty: int,
    order_owner_id: uuid.UUID,
    verified_customer_id: uuid.UUID | None,
    prior_order_refunded: Decimal,
    rules: PolicyRules,
    now: datetime,
    existing_denial: Decision | None = None,
) -> Decision:
    """Return the verdict for refunding `requested_quantity` units of one item.

    `now` is injected for deterministic time tests and never read internally.
    `existing_denial`, if supplied by the tool for a prior terminal denial on
    this item, is re-affirmed unchanged (denials are deterministic and final
    in chat; §9.6). The tool only passes it for genuinely terminal denials, not
    for still-available units on a partially-refunded item.
    """
    if existing_denial is not None:
        return existing_denial

    units_for_amount = requested_quantity if requested_quantity > 0 else 0
    amount = _money(item.unit_price * units_for_amount)
    remaining = item.quantity - already_refunded_qty

    # 1. OWNERSHIP — security gate; a non-owner learns nothing about the item.
    if verified_customer_id is None or verified_customer_id != order_owner_id:
        return Decision(
            outcome=Outcome.DENY,
            reason_code=ReasonCode.DENIED_NOT_OWNER,
            message="This order isn't associated with your verified account, so it can't be refunded here.",
            quantity=requested_quantity,
            amount=amount,
            policy_refs=["ownership"],
            dispute_email=rules.dispute_email,
        )

    # 2. FULLY REFUNDED — current state dominates; nothing left to do.
    if remaining <= 0:
        return Decision(
            outcome=Outcome.DENY,
            reason_code=ReasonCode.DENIED_FULLY_REFUNDED,
            message="All units of this item have already been refunded.",
            quantity=requested_quantity,
            amount=amount,
            policy_refs=["fully_refunded"],
            dispute_email=rules.dispute_email,
        )

    # 3. VALID QUANTITY — reject malformed requests so the customer can correct.
    if requested_quantity <= 0 or requested_quantity > remaining:
        return Decision(
            outcome=Outcome.NEEDS_INFO,
            reason_code=ReasonCode.NEEDS_INFO_INVALID_QUANTITY,
            message=f"Please request between 1 and {remaining} unit(s) for this item.",
            quantity=requested_quantity,
            amount=amount,
            policy_refs=["valid_quantity"],
        )

    # 4. FINAL SALE — terminal, immediately knowable no.
    if item.is_final_sale and not rules.final_sale_refundable:
        return Decision(
            outcome=Outcome.DENY,
            reason_code=ReasonCode.DENIED_FINAL_SALE,
            message="This item was a final-sale purchase and is not eligible for a refund.",
            quantity=requested_quantity,
            amount=amount,
            policy_refs=["final_sale_refundable"],
            dispute_email=rules.dispute_email,
        )

    # 5. NOT DELIVERED — can't start the window; re-evaluable after delivery.
    if item.delivered_at is None:
        return Decision(
            outcome=Outcome.NEEDS_INFO,
            reason_code=ReasonCode.NEEDS_INFO_NOT_DELIVERED,
            message="This item hasn't been delivered yet, so it isn't eligible for a return until after delivery.",
            quantity=requested_quantity,
            amount=amount,
            policy_refs=["not_delivered"],
        )

    # 6. WINDOW — measured from THIS item's delivery; inclusive of the last day.
    if _days_between(item.delivered_at, now) > item.return_window_days:
        return Decision(
            outcome=Outcome.DENY,
            reason_code=ReasonCode.DENIED_WINDOW_EXPIRED,
            message="The return window for this item has closed, so it's no longer eligible for a refund.",
            quantity=requested_quantity,
            amount=amount,
            policy_refs=["return_window_days", "default_return_window_days"],
            dispute_email=rules.dispute_email,
        )

    # 7. THRESHOLD — escalate only an otherwise-eligible refund whose projected
    #    per-order total crosses the limit. Strictly `>` (exactly $500 approves).
    if prior_order_refunded + amount > rules.escalation_threshold_usd:
        return Decision(
            outcome=Outcome.ESCALATE,
            reason_code=ReasonCode.ESCALATED_OVER_THRESHOLD,
            message="This refund would exceed the per-order limit, so it's been routed to a human specialist.",
            quantity=requested_quantity,
            amount=amount,
            policy_refs=["escalation_threshold_usd"],
        )

    # 8. APPROVE.
    return Decision(
        outcome=Outcome.APPROVE,
        reason_code=ReasonCode.APPROVED,
        message=f"Refund approved for {requested_quantity} unit(s).",
        quantity=requested_quantity,
        amount=amount,
        policy_refs=["approved"],
    )
