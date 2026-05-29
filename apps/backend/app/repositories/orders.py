"""Data access for orders / order_items (no business rules)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Order, OrderItem


def get_order_by_number(session: Session, order_number: str) -> Order | None:
    return session.scalar(
        select(Order)
        .where(Order.order_number == order_number)
        .options(selectinload(Order.items))
    )


def list_orders_for_customer(session: Session, customer_id: uuid.UUID) -> list[Order]:
    return list(
        session.scalars(
            select(Order)
            .where(Order.customer_id == customer_id)
            .options(selectinload(Order.items))
            .order_by(Order.ordered_at.desc())
        )
    )


def lock_order(session: Session, order_id: uuid.UUID) -> Order | None:
    """SELECT ... FOR UPDATE on the order row (serializes refunds per order)."""
    return session.scalar(select(Order).where(Order.id == order_id).with_for_update())


def lock_item(session: Session, item_id: uuid.UUID) -> OrderItem | None:
    """SELECT ... FOR UPDATE on the item row."""
    return session.scalar(
        select(OrderItem).where(OrderItem.id == item_id).with_for_update()
    )
