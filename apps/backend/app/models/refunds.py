"""refunds: a terminal decision on a request for N units of one line item.

docs/components/01 §4.4. Deliberately NO UNIQUE(order_id)/UNIQUE(order_item_id):
partial quantity means multiple legitimate refunds per item. Integrity is the
quantity invariant (§7), enforced under a row lock in spec #3 — not by an index.
order_id is denormalized so per-order threshold aggregation is a single indexed
SUM with no join.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin

REFUND_STATUSES = ("approved", "denied", "escalated")
DECIDED_BY = ("agent", "human")


class Refund(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "refunds"

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("order_items.id", ondelete="RESTRICT"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_refs: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    decided_by: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("amount >= 0", name="amount_nonneg"),
        CheckConstraint(
            "status IN ('approved','denied','escalated')", name="status_valid"
        ),
        CheckConstraint(
            "decided_by IN ('agent','human')", name="decided_by_valid"
        ),
        Index("ix_refunds_order_id", "order_id"),
        Index("ix_refunds_order_item_id", "order_item_id"),
        Index("ix_refunds_customer_id", "customer_id"),
        Index("ix_refunds_status", "status"),
    )
