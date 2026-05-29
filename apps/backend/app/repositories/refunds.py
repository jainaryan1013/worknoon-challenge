"""Data access for refunds (no business rules).

Aggregations here back the quantity invariant and the per-order threshold;
the *decisions* live in the rule engine (#2), never here.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Refund


def approved_units_for_item(session: Session, item_id: uuid.UUID) -> int:
    return session.scalar(
        select(func.coalesce(func.sum(Refund.quantity), 0)).where(
            Refund.order_item_id == item_id, Refund.status == "approved"
        )
    )


def approved_total_for_order(session: Session, order_id: uuid.UUID) -> Decimal:
    return session.scalar(
        select(func.coalesce(func.sum(Refund.amount), 0)).where(
            Refund.order_id == order_id, Refund.status == "approved"
        )
    )


def latest_terminal_denial_for_item(session: Session, item_id: uuid.UUID) -> Refund | None:
    return session.scalar(
        select(Refund)
        .where(Refund.order_item_id == item_id, Refund.status == "denied")
        .order_by(Refund.created_at.desc())
    )


def escalated_for_item(session: Session, item_id: uuid.UUID) -> Refund | None:
    return session.scalar(
        select(Refund)
        .where(Refund.order_item_id == item_id, Refund.status == "escalated")
        .order_by(Refund.created_at.desc())
    )


def create_refund(session: Session, **kwargs) -> Refund:
    refund = Refund(**kwargs)
    session.add(refund)
    session.flush()
    return refund
