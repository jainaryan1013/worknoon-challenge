"""Deterministic enforcement attacks (docs/components/08 §3.1) — no LLM.

Each attack hits the tool + rule layer directly and asserts on persisted state
/ outcome, then re-checks the global invariant. These are the binding
guarantees and run on every change.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.models import Customer, Order, OrderItem, Refund
from app.repositories import conversations as conversations_repo
from app.repositories import customers as customers_repo
from app.seed import seed
from app.services import policy_service, refund_service
from app.tools.context import ToolContext
from app.tools.lookup import get_order_details
from app.tools.refund import process_refund
from app.tools.return_options import present_return_options
from tests.adversarial.test_invariants import assert_no_unauthorized_refunds

NOW = datetime.now(timezone.utc)
_TABLES = "refunds, agent_steps, messages, order_items, orders, conversations, customers, policy_rules, policy_documents"


@pytest.fixture()
def seeded(db):
    seed.run(db)
    return db


def ctx_for(db, customer_id: uuid.UUID | None = None) -> ToolContext:
    conv = conversations_repo.create(db)
    return ToolContext(db=db, conversation_id=conv.id, verified_customer_id=customer_id)


def cid(db, email: str) -> uuid.UUID:
    return customers_repo.get_by_email(db, email).id


def approved_count(db, order_number: str | None = None) -> int:
    q = select(func.count()).select_from(Refund).where(Refund.status == "approved")
    if order_number:
        q = q.join(Order, Refund.order_id == Order.id).where(Order.order_number == order_number)
    return db.scalar(q)


def build_order(db, *, email: str, order_number: str, items: list[dict]) -> uuid.UUID:
    customer = Customer(name="Mallory", email=email, loyalty_tier="standard")
    db.add(customer)
    db.flush()
    order = Order(
        customer_id=customer.id, order_number=order_number, status="delivered",
        total_amount=Decimal("0.00"), ordered_at=NOW - timedelta(days=10),
    )
    db.add(order)
    db.flush()
    for it in items:
        db.add(
            OrderItem(
                order_id=order.id, product_name=it["name"], sku=it["sku"],
                quantity=it.get("qty", 1), unit_price=Decimal(it["price"]),
                is_final_sale=it.get("final", False),
                delivered_at=NOW - timedelta(days=it.get("delivered_days", 5)),
            )
        )
    db.flush()
    return customer.id


# --- attack: final-sale refund ---------------------------------------------

def test_final_sale_is_denied(seeded):
    ctx = ctx_for(seeded, cid(seeded, "ben@example.com"))
    res = process_refund(ctx, {"order_number": "ORD-1002", "line_ref": "Clearance Tee", "quantity": 1})
    assert res.data["outcome"] == "DENY" and res.data["reason_code"] == "DENIED_FINAL_SALE"
    assert approved_count(seeded, "ORD-1002") == 0
    assert_no_unauthorized_refunds(seeded)


# --- attack: window expired -------------------------------------------------

def test_window_expired_is_denied(seeded):
    ctx = ctx_for(seeded, cid(seeded, "cara@example.com"))
    res = process_refund(ctx, {"order_number": "ORD-1003", "line_ref": "Desk Lamp", "quantity": 1})
    assert res.data["reason_code"] == "DENIED_WINDOW_EXPIRED"
    assert approved_count(seeded, "ORD-1003") == 0
    assert_no_unauthorized_refunds(seeded)


# --- attack: cross-customer enumeration -------------------------------------

def test_cross_customer_order_is_not_found(seeded):
    ada = cid(seeded, "ada@example.com")
    ctx = ctx_for(seeded, ada)  # verified as Ada, targets Ben's order
    details = get_order_details(ctx, {"order_number": "ORD-1002"})
    refund = process_refund(ctx, {"order_number": "ORD-1002", "line_ref": "Clearance Tee", "quantity": 1})
    assert details.error.code == "order_not_found"
    assert refund.error.code == "order_not_found"
    assert approved_count(seeded, "ORD-1002") == 0
    assert_no_unauthorized_refunds(seeded)


# --- attack: act before verifying identity ----------------------------------

def test_action_before_identity_is_blocked(seeded):
    ctx = ctx_for(seeded, customer_id=None)  # unverified
    res = process_refund(ctx, {"order_number": "ORD-1001", "line_ref": "Wireless Mouse", "quantity": 1})
    assert res.error.code == "identity_required"
    assert approved_count(seeded) == 4  # only the seed's historical approvals
    assert_no_unauthorized_refunds(seeded)


# --- attack: spoofed amount / approved fields -------------------------------

def test_spoofed_amount_field_is_ignored(seeded):
    ctx = ctx_for(seeded, cid(seeded, "ada@example.com"))
    res = process_refund(ctx, {
        "order_number": "ORD-1001", "line_ref": "Wireless Mouse", "quantity": 1,
        "amount": 9999, "approved": True, "decided_by": "human",
    })
    assert res.data["outcome"] == "APPROVE"
    assert res.data["amount"] == "120.00"  # server-computed, not 9999
    assert_no_unauthorized_refunds(seeded)


# --- attack: over-threshold single request ----------------------------------

def test_over_threshold_single_escalates(seeded):
    owner = build_order(
        seeded, email="big@example.com", order_number="ORD-BIG",
        items=[{"name": "Gaming Laptop", "sku": "SKU-LAP", "price": "900.00"}],
    )
    ctx = ctx_for(seeded, owner)
    res = process_refund(ctx, {"order_number": "ORD-BIG", "line_ref": "Gaming Laptop", "quantity": 1})
    assert res.data["outcome"] == "ESCALATE"
    assert approved_count(seeded, "ORD-BIG") == 0
    assert_no_unauthorized_refunds(seeded)


# --- attack: threshold evasion by splitting ---------------------------------

def test_threshold_evasion_by_split_escalates_the_tipping_request(seeded):
    owner = build_order(
        seeded, email="split@example.com", order_number="ORD-SPLIT",
        items=[
            {"name": "Item A", "sku": "SKU-A", "price": "300.00"},
            {"name": "Item B", "sku": "SKU-B", "price": "300.00"},
        ],
    )
    ctx = ctx_for(seeded, owner)
    a = process_refund(ctx, {"order_number": "ORD-SPLIT", "line_ref": "Item A", "quantity": 1})
    b = process_refund(ctx, {"order_number": "ORD-SPLIT", "line_ref": "Item B", "quantity": 1})
    assert a.data["outcome"] == "APPROVE"          # 300 <= 500
    assert b.data["outcome"] == "ESCALATE"         # projected 600 > 500
    assert approved_count(seeded, "ORD-SPLIT") == 1
    assert_no_unauthorized_refunds(seeded)


# --- attack: over-quantity --------------------------------------------------

def test_over_quantity_needs_info(seeded):
    ctx = ctx_for(seeded, cid(seeded, "ada@example.com"))
    # Keyboard qty 3, 1 already refunded by seed -> 2 remain; request 5.
    res = process_refund(ctx, {"order_number": "ORD-1001", "line_ref": "Mechanical Keyboard", "quantity": 5})
    assert res.data["reason_code"] == "NEEDS_INFO_INVALID_QUANTITY"
    assert_no_unauthorized_refunds(seeded)


# --- attack: denial re-request ----------------------------------------------

def test_denial_re_request_returns_prior_denial(seeded):
    ctx = ctx_for(seeded, cid(seeded, "ben@example.com"))
    first = process_refund(ctx, {"order_number": "ORD-1002", "line_ref": "Clearance Tee", "quantity": 1})
    second = process_refund(ctx, {"order_number": "ORD-1002", "line_ref": "Clearance Tee", "quantity": 1})
    assert first.data["reason_code"] == second.data["reason_code"] == "DENIED_FINAL_SALE"
    assert approved_count(seeded, "ORD-1002") == 0
    assert_no_unauthorized_refunds(seeded)


# --- attack: eligibility-hint bypass ----------------------------------------

def test_eligibility_hint_is_not_authority(seeded):
    ctx = ctx_for(seeded, cid(seeded, "ben@example.com"))
    options = present_return_options(ctx, {"order_number": "ORD-1002"})
    hints = {i["line_ref"]: i["eligibility"] for i in options.data["items"]}
    assert hints["Clearance Tee"] == "final_sale"  # UI hint says ineligible
    # Forcing the refund anyway is still denied by the rule engine.
    forced = process_refund(ctx, {"order_number": "ORD-1002", "line_ref": "Clearance Tee", "quantity": 1})
    assert forced.data["outcome"] == "DENY"
    assert approved_count(seeded, "ORD-1002") == 0
    assert_no_unauthorized_refunds(seeded)


# --- attack: double-refund race (real concurrency) --------------------------

def test_double_refund_race_never_over_refunds(engine):
    """Two parallel process_refund calls on a 1-unit item: exactly one approves."""
    Maker = sessionmaker(bind=engine, expire_on_commit=False)
    with Maker() as s:
        customer = Customer(name="Race", email="race-adv@example.com", loyalty_tier="standard")
        s.add(customer)
        s.flush()
        order = Order(customer_id=customer.id, order_number="ORD-RACE-ADV", status="delivered",
                      total_amount=Decimal("50.00"), ordered_at=NOW - timedelta(days=10))
        s.add(order)
        s.flush()
        item = OrderItem(order_id=order.id, product_name="Race Item", sku="SKU-RACE-ADV",
                         quantity=1, unit_price=Decimal("50.00"), delivered_at=NOW - timedelta(days=5))
        s.add(item)
        s.commit()
        customer_id, item_id = customer.id, item.id

    rules = policy_service.from_constants()
    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    errors: list[str] = []

    def worker():
        session: Session = Maker()
        try:
            session.execute(text("SET lock_timeout = '5s'"))
            barrier.wait()
            verdict = refund_service.process_refund(
                session, order_number="ORD-RACE-ADV", line_ref="Race Item", quantity=1,
                verified_customer_id=customer_id, conversation_id=None, rules=rules,
            )
            session.commit()
            outcomes.append(verdict.outcome.value)
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            errors.append(repr(exc))
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)

    try:
        assert not errors, errors
        assert sorted(outcomes) == ["APPROVE", "DENY"]
        with Maker() as s:
            units = s.scalar(
                select(func.coalesce(func.sum(Refund.quantity), 0)).where(
                    Refund.order_item_id == item_id, Refund.status == "approved"
                )
            )
            assert units == 1  # never 2
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {_TABLES} RESTART IDENTITY CASCADE"))
