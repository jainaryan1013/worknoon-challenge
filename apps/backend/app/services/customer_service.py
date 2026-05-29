"""Customer/order read logic + identity binding (docs/components/03).

Read-only except verify_identity, which binds conversation.customer_id. No
business rules live here; refund verdicts come from the rule engine via
refund_service.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Conversation, Order, OrderItem
from app.repositories import customers as customers_repo
from app.repositories import orders as orders_repo
from app.repositories import refunds as refunds_repo
from app.services import line_ref as line_ref_mod
from app.services.errors import ServiceError
from app.services.rule_engine import ItemFacts, Outcome, PolicyRules, ReasonCode, decision


def _refund_state(approved: int, quantity: int) -> str:
    if approved <= 0:
        return "none"
    if approved >= quantity:
        return "full"
    return "partial"


def verify_identity(
    session: Session, conv: Conversation, order_number: str, email: str
) -> object | None:
    """Bind identity if order_number + email match. Returns the Customer on
    success, None on any failure (caller emits a generic message — §3.1
    anti-enumeration). Re-binding a conversation to a different customer fails.
    """
    order = orders_repo.get_order_by_number(session, order_number)
    if order is None:
        return None
    customer = customers_repo.get_by_id(session, order.customer_id)
    if customer is None or customer.email.strip().lower() != email.strip().lower():
        return None
    if conv.customer_id is not None and conv.customer_id != customer.id:
        return None  # conversation is bound to one identity
    conv.customer_id = customer.id
    session.flush()
    return customer


def require_owned_order(  # noqa: D401 - public helper, reused by refund_service
    session: Session, order_number: str, verified_customer_id: uuid.UUID
) -> Order:
    """Fetch an order, re-checking ownership. Returns order_not_found for both
    a missing order and one owned by someone else (no cross-customer enum)."""
    order = orders_repo.get_order_by_number(session, order_number)
    if order is None or order.customer_id != verified_customer_id:
        raise ServiceError("order_not_found", "We couldn't find that order on your account.")
    return order


def lookup_orders(session: Session, verified_customer_id: uuid.UUID) -> list[dict]:
    orders = orders_repo.list_orders_for_customer(session, verified_customer_id)
    return [
        {
            "order_number": o.order_number,
            "status": o.status,
            "ordered_at": o.ordered_at.isoformat(),
            "total_amount": str(o.total_amount),
            "currency": o.currency,
            "item_count": len(o.items),
        }
        for o in orders
    ]


def _item_detail(session: Session, items: list[OrderItem], item: OrderItem) -> dict:
    approved = refunds_repo.approved_units_for_item(session, item.id)
    remaining = item.quantity - approved
    return {
        "line_ref": line_ref_mod.label_for(items, item),
        "product_name": item.product_name,
        "category": item.category,
        "unit_price": str(item.unit_price),
        "quantity": item.quantity,
        "is_final_sale": item.is_final_sale,
        "return_window_days": item.return_window_days,
        "delivered_at": item.delivered_at.isoformat() if item.delivered_at else None,
        "refunded_quantity": approved,
        "remaining_quantity": remaining,
        "refund_state": _refund_state(approved, item.quantity),
    }


def get_order_details(
    session: Session, order_number: str, verified_customer_id: uuid.UUID
) -> dict:
    order = require_owned_order(session, order_number, verified_customer_id)
    items = list(order.items)
    item_dicts = [_item_detail(session, items, it) for it in items]
    refunded_total = refunds_repo.approved_total_for_order(session, order.id)
    states = {d["refund_state"] for d in item_dicts}
    if states == {"none"}:
        order_state = "none"
    elif states <= {"full"}:
        order_state = "full"
    else:
        order_state = "partial"
    return {
        "order_number": order.order_number,
        "status": order.status,
        "derived_refund_state": order_state,
        "refunded_total": str(refunded_total),
        "items": item_dicts,
    }


_HINT_BY_REASON = {
    ReasonCode.DENIED_FINAL_SALE: "final_sale",
    ReasonCode.DENIED_WINDOW_EXPIRED: "window_expired",
    ReasonCode.NEEDS_INFO_NOT_DELIVERED: "not_delivered",
}


def present_return_options(
    session: Session,
    order_number: str,
    verified_customer_id: uuid.UUID,
    rules: PolicyRules,
    *,
    now: datetime | None = None,
) -> dict:
    """Returnable items (remaining > 0) annotated with a UI eligibility hint.
    Read-only; the binding check still happens in process_refund (§3.7b)."""
    now = now or datetime.now(timezone.utc)
    order = require_owned_order(session, order_number, verified_customer_id)
    items = list(order.items)
    prior_total = refunds_repo.approved_total_for_order(session, order.id)
    out_items = []
    for item in items:
        approved = refunds_repo.approved_units_for_item(session, item.id)
        remaining = item.quantity - approved
        if remaining <= 0:
            continue
        d = decision(
            item=ItemFacts(
                id=item.id,
                order_id=order.id,
                is_final_sale=item.is_final_sale,
                return_window_days=item.return_window_days,
                unit_price=item.unit_price,
                quantity=item.quantity,
                delivered_at=item.delivered_at,
            ),
            requested_quantity=remaining,
            already_refunded_qty=approved,
            order_owner_id=order.customer_id,
            verified_customer_id=verified_customer_id,
            prior_order_refunded=prior_total,
            rules=rules,
            now=now,
        )
        hint = "eligible" if d.outcome in (Outcome.APPROVE, Outcome.ESCALATE) else _HINT_BY_REASON.get(d.reason_code, "eligible")
        out_items.append(
            {
                "line_ref": line_ref_mod.label_for(items, item),
                "product_name": item.product_name,
                "unit_price": str(item.unit_price),
                "remaining_quantity": remaining,
                "eligibility": hint,
                "eligibility_note": d.message,
            }
        )
    return {
        "order_number": order.order_number,
        "items": out_items,
        "threshold_usd": str(rules.escalation_threshold_usd),
        "already_refunded_total": str(prior_total),
    }
