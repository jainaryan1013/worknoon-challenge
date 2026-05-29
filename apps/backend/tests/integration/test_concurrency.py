"""Concurrent process_refund on the same item must not over-refund.

Unlike the other integration tests (single rolled-back transaction), this one
uses TWO real sessions that COMMIT, so the SELECT ... FOR UPDATE lock is
actually exercised. It cleans up via TRUNCATE so the shared schema is left
pristine for other tests.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.models import Customer, Order, OrderItem
from app.repositories import refunds as refunds_repo
from app.services import policy_service, refund_service

TABLES = "refunds, agent_steps, messages, order_items, orders, conversations, customers, policy_rules, policy_documents"


@pytest.fixture()
def race_setup(engine):
    """Commit one customer/order/item (qty 1, eligible). Yield ids; truncate after."""
    Maker = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    with Maker() as s:
        customer = Customer(name="Race", email="race@example.com", loyalty_tier="standard")
        s.add(customer)
        s.flush()
        order = Order(
            customer_id=customer.id, order_number="ORD-RACE", status="delivered",
            total_amount=Decimal("50.00"), ordered_at=now - timedelta(days=10),
        )
        s.add(order)
        s.flush()
        item = OrderItem(
            order_id=order.id, product_name="Race Item", sku="SKU-RACE",
            quantity=1, unit_price=Decimal("50.00"), delivered_at=now - timedelta(days=5),
        )
        s.add(item)
        s.commit()
        ids = (customer.id, item.id)
    try:
        yield Maker, ids
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))


def test_concurrent_refund_does_not_over_refund(race_setup):
    Maker, (customer_id, item_id) = race_setup
    rules = policy_service.from_constants()
    barrier = threading.Barrier(2)
    results: list = []
    errors: list = []

    def worker():
        session: Session = Maker()
        try:
            session.execute(text("SET lock_timeout = '5s'"))
            barrier.wait()
            verdict = refund_service.process_refund(
                session,
                order_number="ORD-RACE",
                line_ref="Race Item",
                quantity=1,
                verified_customer_id=customer_id,
                conversation_id=None,
                rules=rules,
            )
            session.commit()
            results.append(verdict.outcome.value)
        except Exception as exc:  # noqa: BLE001 - surface as a test failure
            session.rollback()
            errors.append(repr(exc))
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)

    assert not errors, errors
    assert sorted(results) == ["APPROVE", "DENY"]

    # The invariant: exactly one unit refunded, never two.
    with Maker() as s:
        assert refunds_repo.approved_units_for_item(s, item_id) == 1
