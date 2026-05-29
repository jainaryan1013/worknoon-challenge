"""Executable specification of refund policy (docs/components/02 §8).

Pure, no DB. Table-driven over every precedence branch and boundary.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.services import policy_service
from app.services.rule_engine import (
    Decision,
    ItemFacts,
    Outcome,
    ReasonCode,
    decision,
)

NOW = datetime(2026, 5, 29, 12, 0, 0, tzinfo=timezone.utc)
OWNER = uuid.uuid4()
RULES = policy_service.from_constants()  # threshold 500, window 30, final-sale off


def make_item(
    *,
    unit_price: str = "50.00",
    quantity: int = 2,
    is_final_sale: bool = False,
    return_window_days: int = 30,
    delivered_days_ago: int | None = 5,
) -> ItemFacts:
    delivered = None if delivered_days_ago is None else NOW - timedelta(days=delivered_days_ago)
    return ItemFacts(
        id=uuid.uuid4(),
        order_id=uuid.uuid4(),
        is_final_sale=is_final_sale,
        return_window_days=return_window_days,
        unit_price=Decimal(unit_price),
        quantity=quantity,
        delivered_at=delivered,
    )


def run(
    item: ItemFacts,
    *,
    requested_quantity: int = 1,
    already_refunded_qty: int = 0,
    verified_customer_id: uuid.UUID | None = OWNER,
    prior_order_refunded: str = "0",
) -> Decision:
    return decision(
        item=item,
        requested_quantity=requested_quantity,
        already_refunded_qty=already_refunded_qty,
        order_owner_id=OWNER,
        verified_customer_id=verified_customer_id,
        prior_order_refunded=Decimal(prior_order_refunded),
        rules=RULES,
        now=NOW,
    )


def test_no_identity_denies_not_owner():
    d = run(make_item(), verified_customer_id=None)
    assert d.outcome is Outcome.DENY
    assert d.reason_code is ReasonCode.DENIED_NOT_OWNER
    assert d.dispute_email == RULES.dispute_email


def test_wrong_owner_denies_not_owner():
    d = run(make_item(), verified_customer_id=uuid.uuid4())
    assert (d.outcome, d.reason_code) == (Outcome.DENY, ReasonCode.DENIED_NOT_OWNER)


def test_fully_refunded_denies():
    d = run(make_item(quantity=2), already_refunded_qty=2)
    assert (d.outcome, d.reason_code) == (Outcome.DENY, ReasonCode.DENIED_FULLY_REFUNDED)


def test_inconsistent_overrefund_denies_fully_refunded():
    # already_refunded_qty > quantity -> remaining < 0 -> fail closed, never approve
    d = run(make_item(quantity=2), already_refunded_qty=5)
    assert (d.outcome, d.reason_code) == (Outcome.DENY, ReasonCode.DENIED_FULLY_REFUNDED)


def test_zero_quantity_needs_info():
    d = run(make_item(quantity=3), requested_quantity=0)
    assert (d.outcome, d.reason_code) == (Outcome.NEEDS_INFO, ReasonCode.NEEDS_INFO_INVALID_QUANTITY)


def test_over_remaining_quantity_needs_info():
    d = run(make_item(quantity=3), requested_quantity=5, already_refunded_qty=1)
    assert (d.outcome, d.reason_code) == (Outcome.NEEDS_INFO, ReasonCode.NEEDS_INFO_INVALID_QUANTITY)


def test_final_sale_denies():
    d = run(make_item(is_final_sale=True))
    assert (d.outcome, d.reason_code) == (Outcome.DENY, ReasonCode.DENIED_FINAL_SALE)


def test_final_sale_precedes_not_delivered():
    d = run(make_item(is_final_sale=True, delivered_days_ago=None))
    assert (d.outcome, d.reason_code) == (Outcome.DENY, ReasonCode.DENIED_FINAL_SALE)


def test_not_delivered_needs_info():
    d = run(make_item(delivered_days_ago=None))
    assert (d.outcome, d.reason_code) == (Outcome.NEEDS_INFO, ReasonCode.NEEDS_INFO_NOT_DELIVERED)


def test_window_expired_denies():
    d = run(make_item(delivered_days_ago=60, return_window_days=30))
    assert (d.outcome, d.reason_code) == (Outcome.DENY, ReasonCode.DENIED_WINDOW_EXPIRED)


def test_boundary_exactly_window_approves():
    # delivered exactly 30 days ago, window 30 -> still eligible (`>` not `>=`)
    d = run(make_item(delivered_days_ago=30, return_window_days=30))
    assert d.outcome is Outcome.APPROVE


def test_over_threshold_single_big_escalates():
    d = run(make_item(unit_price="600.00", quantity=1), requested_quantity=1)
    assert (d.outcome, d.reason_code) == (Outcome.ESCALATE, ReasonCode.ESCALATED_OVER_THRESHOLD)


def test_over_threshold_accumulated_escalates():
    d = run(make_item(unit_price="150.00", quantity=1), prior_order_refunded="400")
    assert (d.outcome, d.reason_code) == (Outcome.ESCALATE, ReasonCode.ESCALATED_OVER_THRESHOLD)


def test_boundary_exactly_500_approves():
    d = run(make_item(unit_price="500.00", quantity=1), prior_order_refunded="0")
    assert d.outcome is Outcome.APPROVE
    assert d.amount == Decimal("500.00")


def test_boundary_prior_450_plus_50_approves():
    d = run(make_item(unit_price="50.00", quantity=1), prior_order_refunded="450")
    assert d.outcome is Outcome.APPROVE


def test_partial_approve_sets_requested_quantity():
    d = run(make_item(unit_price="20.00", quantity=3), requested_quantity=1)
    assert d.outcome is Outcome.APPROVE
    assert d.quantity == 1
    assert d.amount == Decimal("20.00")


def test_happy_path_approves():
    d = run(make_item(unit_price="120.00", quantity=1))
    assert (d.outcome, d.reason_code) == (Outcome.APPROVE, ReasonCode.APPROVED)
    assert d.dispute_email is None


def test_existing_denial_is_reaffirmed():
    prior = Decision(
        outcome=Outcome.DENY,
        reason_code=ReasonCode.DENIED_WINDOW_EXPIRED,
        message="window closed",
        quantity=1,
        amount=Decimal("0.00"),
        policy_refs=["return_window_days"],
        dispute_email=RULES.dispute_email,
    )
    d = decision(
        item=make_item(),
        requested_quantity=1,
        already_refunded_qty=0,
        order_owner_id=OWNER,
        verified_customer_id=OWNER,
        prior_order_refunded=Decimal("0"),
        rules=RULES,
        now=NOW,
        existing_denial=prior,
    )
    assert d is prior


@pytest.mark.parametrize("amount_str,prior,expected", [
    ("500.00", "0", Outcome.APPROVE),
    ("500.01", "0", Outcome.ESCALATE),
    ("0.01", "500.00", Outcome.ESCALATE),
])
def test_threshold_is_strict_greater_than(amount_str, prior, expected):
    d = run(make_item(unit_price=amount_str, quantity=1), prior_order_refunded=prior)
    assert d.outcome is expected
