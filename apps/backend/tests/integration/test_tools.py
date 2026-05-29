"""Tools layer: gates, ownership, the process_refund transaction, re-request
guard, and the enforcement-matrix behaviors (docs/components/03 §5, §7)."""

from __future__ import annotations

import uuid

import pytest

from app.repositories import conversations as conversations_repo
from app.repositories import customers as customers_repo
from app.seed import seed
from app.tools.context import ToolContext
from app.tools.eligibility import check_refund_eligibility
from app.tools.escalate import escalate_to_human
from app.tools.identity import verify_identity
from app.tools.lookup import get_order_details, lookup_orders
from app.tools.refund import process_refund
from app.tools.return_options import present_return_options


@pytest.fixture()
def seeded(db):
    seed.run(db)
    return db


def ctx_for(db, customer_id: uuid.UUID | None = None) -> ToolContext:
    conv = conversations_repo.create(db)
    return ToolContext(db=db, conversation_id=conv.id, verified_customer_id=customer_id)


def cid(db, email: str) -> uuid.UUID:
    return customers_repo.get_by_email(db, email).id


# --- identity & gates -------------------------------------------------------

def test_identity_required_gate(seeded):
    res = lookup_orders(ctx_for(seeded), {})
    assert res.ok is False
    assert res.error.code == "identity_required"


def test_verify_identity_success_and_binds(seeded):
    ctx = ctx_for(seeded)
    res = verify_identity(ctx, {"order_number": "ORD-1001", "email": "ADA@example.com"})
    assert res.ok is True
    assert res.data["customer_name"] == "Ada Lovelace"
    assert ctx.verified_customer_id == cid(seeded, "ada@example.com")


def test_verify_identity_wrong_email_is_generic(seeded):
    ctx = ctx_for(seeded)
    res = verify_identity(ctx, {"order_number": "ORD-1001", "email": "nope@example.com"})
    assert res.ok is False
    assert res.error.code == "verification_failed"
    assert ctx.verified_customer_id is None


def test_verify_identity_rejects_rebind_to_other_customer(seeded):
    ctx = ctx_for(seeded, customer_id=None)
    verify_identity(ctx, {"order_number": "ORD-1001", "email": "ada@example.com"})
    # now try to bind same conversation to Ben
    res = verify_identity(ctx, {"order_number": "ORD-1002", "email": "ben@example.com"})
    assert res.ok is False


# --- ownership --------------------------------------------------------------

def test_ownership_other_customers_order_is_not_found(seeded):
    ctx = ctx_for(seeded, customer_id=cid(seeded, "ada@example.com"))
    res = get_order_details(ctx, {"order_number": "ORD-1002"})  # Ben's order
    assert res.ok is False
    assert res.error.code == "order_not_found"


def test_process_refund_other_customers_order_is_not_found(seeded):
    ctx = ctx_for(seeded, customer_id=cid(seeded, "ada@example.com"))
    res = process_refund(ctx, {"order_number": "ORD-1002", "line_ref": "Clearance Tee", "quantity": 1})
    assert res.ok is False
    assert res.error.code == "order_not_found"


# --- process_refund outcomes ------------------------------------------------

def test_happy_path_approves_and_computes_amount(seeded):
    ctx = ctx_for(seeded, customer_id=cid(seeded, "ada@example.com"))
    res = process_refund(ctx, {"order_number": "ORD-1001", "line_ref": "Wireless Mouse", "quantity": 1})
    assert res.ok is True
    assert res.data["outcome"] == "APPROVE"
    assert res.data["amount"] == "120.00"


def test_model_supplied_amount_is_ignored(seeded):
    ctx = ctx_for(seeded, customer_id=cid(seeded, "ada@example.com"))
    res = process_refund(ctx, {
        "order_number": "ORD-1001", "line_ref": "Wireless Mouse", "quantity": 1,
        "amount": 9999, "approved": True, "order_item_id": str(uuid.uuid4()),
    })
    assert res.ok is True
    assert res.data["amount"] == "120.00"  # server-computed, not 9999


def test_final_sale_denies(seeded):
    ctx = ctx_for(seeded, customer_id=cid(seeded, "ben@example.com"))
    res = process_refund(ctx, {"order_number": "ORD-1002", "line_ref": "Clearance Tee", "quantity": 1})
    assert res.data["outcome"] == "DENY"
    assert res.data["reason_code"] == "DENIED_FINAL_SALE"
    assert res.data["dispute_email"]


def test_not_delivered_needs_info_writes_no_row(seeded):
    ctx = ctx_for(seeded, customer_id=cid(seeded, "dan@example.com"))
    res = process_refund(ctx, {"order_number": "ORD-1004", "line_ref": "Standing Fan", "quantity": 1})
    assert res.data["outcome"] == "NEEDS_INFO"
    # re-checking eligibility still says NEEDS_INFO (no terminal row written)
    elig = check_refund_eligibility(ctx, {"order_number": "ORD-1004", "line_ref": "Standing Fan", "quantity": 1})
    assert elig.data["outcome"] == "NEEDS_INFO"


def test_partial_quantity_sequence_then_exhausted(seeded):
    # Keyboard qty 3, 1 already refunded by seed -> 2 remain.
    ctx = ctx_for(seeded, customer_id=cid(seeded, "ada@example.com"))
    a = process_refund(ctx, {"order_number": "ORD-1001", "line_ref": "Mechanical Keyboard", "quantity": 1})
    b = process_refund(ctx, {"order_number": "ORD-1001", "line_ref": "Mechanical Keyboard", "quantity": 1})
    c = process_refund(ctx, {"order_number": "ORD-1001", "line_ref": "Mechanical Keyboard", "quantity": 1})
    assert a.data["outcome"] == "APPROVE"
    assert b.data["outcome"] == "APPROVE"
    assert c.data["outcome"] == "DENY"
    assert c.data["reason_code"] == "DENIED_FULLY_REFUNDED"


def test_threshold_accumulation_escalates(seeded):
    # ORD-1008 already has $480 approved; Cable Kit ($60) tips projected to $540.
    ctx = ctx_for(seeded, customer_id=cid(seeded, "gina@example.com"))
    res = process_refund(ctx, {"order_number": "ORD-1008", "line_ref": "Cable Kit", "quantity": 1})
    assert res.data["outcome"] == "ESCALATE"
    assert res.data["reason_code"] == "ESCALATED_OVER_THRESHOLD"


def test_re_request_after_denial_returns_prior_denial(seeded):
    ctx = ctx_for(seeded, customer_id=cid(seeded, "ben@example.com"))
    first = process_refund(ctx, {"order_number": "ORD-1002", "line_ref": "Clearance Tee", "quantity": 1})
    second = process_refund(ctx, {"order_number": "ORD-1002", "line_ref": "Clearance Tee", "quantity": 1})
    assert first.data["outcome"] == second.data["outcome"] == "DENY"
    assert second.data["reason_code"] == "DENIED_FINAL_SALE"


def test_invalid_quantity_zero_needs_info(seeded):
    ctx = ctx_for(seeded, customer_id=cid(seeded, "ada@example.com"))
    res = process_refund(ctx, {"order_number": "ORD-1001", "line_ref": "Wireless Mouse", "quantity": 0})
    assert res.data["outcome"] == "NEEDS_INFO"
    assert res.data["reason_code"] == "NEEDS_INFO_INVALID_QUANTITY"


# --- previews & discovery ---------------------------------------------------

def test_eligibility_preview_matches_action(seeded):
    ctx = ctx_for(seeded, customer_id=cid(seeded, "ada@example.com"))
    preview = check_refund_eligibility(ctx, {"order_number": "ORD-1001", "line_ref": "Wireless Mouse", "quantity": 1})
    assert preview.ok is True
    assert preview.data["outcome"] == "APPROVE"
    assert preview.data["amount"] == "120.00"


def test_return_options_excludes_fully_refunded(seeded):
    # Finn's mug (ORD-1006) is fully refunded -> should not appear.
    ctx = ctx_for(seeded, customer_id=cid(seeded, "finn@example.com"))
    res = present_return_options(ctx, {"order_number": "ORD-1006"})
    assert res.ok is True
    assert res.data["items"] == []


def test_return_options_hint_final_sale(seeded):
    ctx = ctx_for(seeded, customer_id=cid(seeded, "ben@example.com"))
    res = present_return_options(ctx, {"order_number": "ORD-1002"})
    hints = {i["line_ref"]: i["eligibility"] for i in res.data["items"]}
    assert hints["Clearance Tee"] == "final_sale"
    assert hints["Water Bottle"] == "eligible"


# --- escalation -------------------------------------------------------------

def test_escalate_is_idempotent(seeded):
    ctx = ctx_for(seeded, customer_id=cid(seeded, "ada@example.com"))
    first = escalate_to_human(ctx, {"order_number": "ORD-1001", "line_ref": "Wireless Mouse", "summary": "x"})
    second = escalate_to_human(ctx, {"order_number": "ORD-1001", "line_ref": "Wireless Mouse", "summary": "x"})
    assert first.ok and second.ok
    assert first.data["reference"] == second.data["reference"]
