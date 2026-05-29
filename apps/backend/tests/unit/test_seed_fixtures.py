"""Seeding: counts, idempotency, fixture invariants, policy anti-drift."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select

from app.models import Customer, Order, OrderItem, PolicyRule, Refund
from app.seed import policy_source, seed


def _approved_units(db, order_number: str, sku: str) -> int:
    item = db.scalar(
        select(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .where(Order.order_number == order_number, OrderItem.sku == sku)
    )
    return db.scalar(
        select(func.coalesce(func.sum(Refund.quantity), 0)).where(
            Refund.order_item_id == item.id, Refund.status == "approved"
        )
    ), item


def test_seed_inserts_expected_counts(db):
    assert seed.run(db) is True
    assert db.scalar(select(func.count()).select_from(Customer)) == 15
    assert db.scalar(select(func.count()).select_from(Order)) == 16
    assert db.scalar(select(func.count()).select_from(OrderItem)) == 20
    assert db.scalar(select(func.count()).select_from(Refund)) == 4


def test_seed_is_idempotent(db):
    assert seed.run(db) is True
    db.flush()
    assert seed.run(db) is False  # second run is a no-op
    assert db.scalar(select(func.count()).select_from(Customer)) == 15


def test_boundary_order_projects_exactly_500(db):
    seed.run(db)
    total = db.scalar(
        select(func.coalesce(func.sum(Refund.amount), 0))
        .join(Order, Refund.order_id == Order.id)
        .where(Order.order_number == "ORD-1007", Refund.status == "approved")
    )
    assert total == Decimal("500.00")


def test_over_threshold_order_approved_total(db):
    seed.run(db)
    total = db.scalar(
        select(func.coalesce(func.sum(Refund.amount), 0))
        .join(Order, Refund.order_id == Order.id)
        .where(Order.order_number == "ORD-1008", Refund.status == "approved")
    )
    assert total == Decimal("480.00")


def test_partial_quantity_leaves_units_remaining(db):
    seed.run(db)
    units, item = _approved_units(db, "ORD-1001", "SKU-KEYB")
    assert item.quantity == 3
    assert units == 1  # one unit already refunded, two remain


def test_fully_refunded_item_has_no_remaining(db):
    seed.run(db)
    units, item = _approved_units(db, "ORD-1006", "SKU-MUG")
    assert units == item.quantity == 2


def test_quantity_invariant_holds_for_all_items(db):
    seed.run(db)
    rows = db.execute(
        select(
            OrderItem.id,
            OrderItem.quantity,
            func.coalesce(
                select(func.sum(Refund.quantity))
                .where(Refund.order_item_id == OrderItem.id, Refund.status == "approved")
                .scalar_subquery(),
                0,
            ),
        )
    ).all()
    for _id, qty, approved in rows:
        assert approved <= qty


def test_policy_anti_drift(db):
    seed.run(db)
    threshold = db.scalar(
        select(PolicyRule.value).where(PolicyRule.key == "escalation_threshold_usd")
    )
    assert threshold == policy_source.CONSTANTS.escalation_threshold_usd == 500
    # The prose document must cite the same threshold the rule enforces.
    from app.models import PolicyDocument

    body = db.scalar(select(PolicyDocument.body_markdown))
    assert "$500" in body
    assert "disputes@refundagent.example" in body
