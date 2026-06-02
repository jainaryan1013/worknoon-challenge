"""The global invariant (docs/components/08 §4) — the centerpiece.

For every approved refund, replaying it through the rule engine AS OF its
decision time must yield APPROVE. This is scenario-independent: no matter what
an attack did, the DB never holds a refund the policy forbids. Imported and
called at the end of each enforcement test.

Assert on STATE, never on model prose.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, OrderItem, Refund
from app.seed import seed
from app.services import policy_service
from app.services.rule_engine import ItemFacts, Outcome, PolicyRules, decision


def assert_no_unauthorized_refunds(db: Session, rules: PolicyRules | None = None) -> None:
    """Replay every approved refund chronologically through decision() and
    assert each one is still an APPROVE; plus the structural companions."""
    rules = rules or policy_service.from_constants()

    approved = list(
        db.scalars(
            select(Refund)
            .where(Refund.status == "approved")
            .order_by(Refund.created_at, Refund.id)
        )
    )

    units_before: dict = defaultdict(int)                        # per order_item_id
    amount_before: dict = defaultdict(lambda: Decimal("0.00"))   # per order_id

    for refund in approved:
        item = db.get(OrderItem, refund.order_item_id)
        order = db.get(Order, refund.order_id)
        assert item is not None and order is not None

        now: datetime = refund.created_at
        verdict = decision(
            item=ItemFacts(
                id=item.id,
                order_id=order.id,
                is_final_sale=item.is_final_sale,
                return_window_days=item.return_window_days,
                unit_price=item.unit_price,
                quantity=item.quantity,
                delivered_at=item.delivered_at,
            ),
            requested_quantity=refund.quantity,
            already_refunded_qty=units_before[refund.order_item_id],
            order_owner_id=order.customer_id,
            verified_customer_id=refund.customer_id,
            prior_order_refunded=amount_before[refund.order_id],
            rules=rules,
            now=now,
        )
        assert verdict.outcome is Outcome.APPROVE, (
            f"approved refund {refund.id} replays as {verdict.outcome} "
            f"({verdict.reason_code}) — an unauthorized refund is persisted"
        )
        # amount must be exactly unit_price * quantity (never model-supplied)
        assert refund.amount == item.unit_price * refund.quantity

        units_before[refund.order_item_id] += refund.quantity
        amount_before[refund.order_id] += refund.amount

    # Companions: units never exceed quantity; approved per order never over the cap.
    for item_id, total_units in units_before.items():
        item = db.get(OrderItem, item_id)
        assert total_units <= item.quantity, f"over-refunded units on item {item_id}"
    for order_id, total_amount in amount_before.items():
        assert total_amount <= rules.escalation_threshold_usd, (
            f"order {order_id} approved total {total_amount} exceeds the escalation cap"
        )


def test_seed_data_satisfies_global_invariant(db):
    """The seeded fixtures themselves must contain no unauthorized refund."""
    seed.run(db)
    assert_no_unauthorized_refunds(db)
