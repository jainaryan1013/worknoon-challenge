"""Refund processing — the state-changing core (docs/components/03 §3.5, §3.6).

`process_refund` is the trust boundary's teeth: it locks the order + item,
re-reads live facts, re-derives the verdict via the rule engine (never trusting
the model), writes the matching refund row, and re-asserts the quantity
invariant. It flushes; the caller owns COMMIT (so the lock is held until the
request transaction ends).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Order, OrderItem
from app.repositories import conversations as conversations_repo
from app.repositories import orders as orders_repo
from app.repositories import refunds as refunds_repo
from app.services import customer_service, line_ref as line_ref_mod
from app.services.errors import ServiceError
from app.services.rule_engine import (
    Decision,
    ItemFacts,
    Outcome,
    PolicyRules,
    ReasonCode,
    decision,
)


def _resolve_item(order: Order, line_ref: str) -> OrderItem:
    matches = line_ref_mod.resolve(list(order.items), line_ref)
    if len(matches) == 0:
        raise ServiceError("order_not_found", "We couldn't find that item on the order.")
    if len(matches) > 1:
        raise ServiceError(
            "ambiguous_item",
            "That item name matches more than one line; please re-fetch the order details and use the exact label.",
        )
    return matches[0]


def _facts(item: OrderItem, order: Order) -> ItemFacts:
    return ItemFacts(
        id=item.id,
        order_id=order.id,
        is_final_sale=item.is_final_sale,
        return_window_days=item.return_window_days,
        unit_price=item.unit_price,
        quantity=item.quantity,
        delivered_at=item.delivered_at,
    )


def _denial_decision(denial, rules: PolicyRules) -> Decision:
    """Rebuild the Decision from a stored terminal denial row (re-request guard)."""
    return Decision(
        outcome=Outcome.DENY,
        reason_code=ReasonCode(denial.reason_code),
        message=denial.reason or "This request was previously denied.",
        quantity=denial.quantity,
        amount=denial.amount,
        policy_refs=list(denial.policy_refs or []),
        dispute_email=rules.dispute_email,
    )


def check_eligibility(
    session: Session,
    *,
    order_number: str,
    line_ref: str,
    quantity: int,
    verified_customer_id: uuid.UUID,
    rules: PolicyRules,
    now: datetime | None = None,
) -> Decision:
    """Read-only preview. Shares decision() with process_refund, no writes/locks."""
    now = now or datetime.now(timezone.utc)
    order = customer_service.require_owned_order(session, order_number, verified_customer_id)
    item = _resolve_item(order, line_ref)
    already = refunds_repo.approved_units_for_item(session, item.id)
    prior = refunds_repo.approved_total_for_order(session, order.id)
    denial = refunds_repo.latest_terminal_denial_for_item(session, item.id)
    if denial is not None:
        return _denial_decision(denial, rules)
    return decision(
        item=_facts(item, order),
        requested_quantity=quantity,
        already_refunded_qty=already,
        order_owner_id=order.customer_id,
        verified_customer_id=verified_customer_id,
        prior_order_refunded=prior,
        rules=rules,
        now=now,
    )


def process_refund(
    session: Session,
    *,
    order_number: str,
    line_ref: str,
    quantity: int,
    verified_customer_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    rules: PolicyRules,
    now: datetime | None = None,
) -> Decision:
    """Binding refund for N units of one item. Locks order+item, re-derives the
    verdict under the lock, writes the matching row, re-asserts the invariant.
    Flushes only — caller commits."""
    now = now or datetime.now(timezone.utc)

    # Resolve within the verified customer's order (ownership re-checked).
    order = customer_service.require_owned_order(session, order_number, verified_customer_id)
    item = _resolve_item(order, line_ref)

    # Lock order then item (FOR UPDATE) — serializes concurrent refunds.
    locked_order = orders_repo.lock_order(session, order.id)
    locked_item = orders_repo.lock_item(session, item.id)
    if locked_order is None or locked_item is None:
        raise ServiceError("order_not_found", "We couldn't find that order on your account.")
    if locked_order.customer_id != verified_customer_id:
        raise ServiceError("order_not_found", "We couldn't find that order on your account.")

    # Live facts under the lock.
    already = refunds_repo.approved_units_for_item(session, locked_item.id)
    prior = refunds_repo.approved_total_for_order(session, locked_order.id)
    denial = refunds_repo.latest_terminal_denial_for_item(session, locked_item.id)

    # Re-request guard: a prior terminal denial is final in chat.
    if denial is not None:
        return _denial_decision(denial, rules)

    verdict = decision(
        item=_facts(locked_item, locked_order),
        requested_quantity=quantity,
        already_refunded_qty=already,
        order_owner_id=locked_order.customer_id,
        verified_customer_id=verified_customer_id,
        prior_order_refunded=prior,
        rules=rules,
        now=now,
    )

    if verdict.outcome is Outcome.NEEDS_INFO:
        return verdict  # no row written

    status = {
        Outcome.APPROVE: "approved",
        Outcome.DENY: "denied",
        Outcome.ESCALATE: "escalated",
    }[verdict.outcome]

    # Write-then-verify inside a savepoint so the invariant guard fails CLOSED:
    # if the re-check trips, the savepoint is rolled back and no refund row can
    # survive (even though the lock + rule engine make this path unreachable
    # today). Never leave an over-refund row pending for the caller's COMMIT.
    nested = session.begin_nested()
    try:
        refunds_repo.create_refund(
            session,
            order_id=locked_order.id,
            order_item_id=locked_item.id,
            customer_id=verified_customer_id,
            conversation_id=conversation_id,
            quantity=verdict.quantity,
            amount=verdict.amount if verdict.outcome is not Outcome.DENY else Decimal("0.00"),
            status=status,
            reason_code=verdict.reason_code.value,
            reason=verdict.message,
            policy_refs=list(verdict.policy_refs),
            decided_by="agent",
        )

        if verdict.outcome is Outcome.APPROVE:
            # Re-assert the quantity invariant after consuming units (DB §7).
            approved_after = refunds_repo.approved_units_for_item(session, locked_item.id)
            if approved_after > locked_item.quantity:
                raise ServiceError(
                    "refund_conflict",
                    "This refund could not be completed due to a conflict; please try again.",
                )
        nested.commit()
    except ServiceError:
        nested.rollback()  # drop the just-written row — fail closed
        raise

    if verdict.outcome is Outcome.ESCALATE and conversation_id is not None:
        conv = conversations_repo.get(session, conversation_id)
        if conv is not None:
            conversations_repo.set_status(session, conv, "escalated")

    return verdict


def escalate(
    session: Session,
    *,
    order_number: str,
    line_ref: str | None,
    summary: str,
    verified_customer_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    rules: PolicyRules | None = None,
) -> dict:
    """Idempotent escalation: record one escalated row (if not already present
    for the item) and mark the conversation escalated. Records + informs only."""
    order = customer_service.require_owned_order(session, order_number, verified_customer_id)

    item = None
    if line_ref:
        item = _resolve_item(order, line_ref)
        existing = refunds_repo.escalated_for_item(session, item.id)
        if existing is not None:
            return {"escalated": True, "reference": str(existing.id)}

    qty = 1
    if item is not None:
        qty = max(item.quantity - refunds_repo.approved_units_for_item(session, item.id), 1)

    refund = refunds_repo.create_refund(
        session,
        order_id=order.id,
        order_item_id=item.id if item is not None else _any_item_id(order),
        customer_id=verified_customer_id,
        conversation_id=conversation_id,
        quantity=qty,
        amount=Decimal("0.00"),
        status="escalated",
        reason_code=ReasonCode.ESCALATED_OVER_THRESHOLD.value,
        reason=summary or "Escalated to a human specialist.",
        policy_refs=["escalation_manual"],
        decided_by="agent",
    )
    if conversation_id is not None:
        conv = conversations_repo.get(session, conversation_id)
        if conv is not None:
            conversations_repo.set_status(session, conv, "escalated")
    return {"escalated": True, "reference": str(refund.id)}


def _any_item_id(order: Order) -> uuid.UUID:
    """Escalation requires a non-null order_item_id; use the first line when the
    escalation isn't item-specific (a whole-order hand-off)."""
    return sorted(order.items, key=lambda i: i.sku)[0].id
