"""CHECK / enum constraints reject invalid rows at the DB layer."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Customer, Order, OrderItem


def _customer(db) -> Customer:
    c = Customer(name="Test", email="t@example.com", loyalty_tier="standard")
    db.add(c)
    db.flush()
    return c


def _order(db, customer) -> Order:
    o = Order(
        customer_id=customer.id,
        order_number="ORD-TEST",
        status="delivered",
        total_amount=Decimal("10.00"),
        ordered_at=datetime.now(timezone.utc),
    )
    db.add(o)
    db.flush()
    return o


def test_invalid_loyalty_tier_rejected(db):
    db.add(Customer(name="x", email="x@example.com", loyalty_tier="platinum"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_invalid_order_status_rejected(db):
    c = _customer(db)
    db.add(
        Order(
            customer_id=c.id,
            order_number="ORD-BAD",
            status="refunded",  # not an allowed fulfillment status
            total_amount=Decimal("10.00"),
            ordered_at=datetime.now(timezone.utc),
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_non_positive_quantity_rejected(db):
    c = _customer(db)
    o = _order(db, c)
    db.add(
        OrderItem(
            order_id=o.id,
            product_name="x",
            sku="SKU-X",
            quantity=0,  # violates quantity > 0
            unit_price=Decimal("5.00"),
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_negative_total_amount_rejected(db):
    c = _customer(db)
    db.add(
        Order(
            customer_id=c.id,
            order_number="ORD-NEG",
            status="placed",
            total_amount=Decimal("-1.00"),  # violates total_amount >= 0
            ordered_at=datetime.now(timezone.utc),
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_duplicate_email_rejected(db):
    _customer(db)
    db.add(Customer(name="dup", email="t@example.com", loyalty_tier="gold"))
    with pytest.raises(IntegrityError):
        db.flush()
