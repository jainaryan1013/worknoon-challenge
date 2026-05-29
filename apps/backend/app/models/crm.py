"""CRM tables: customers, orders, order_items.

Per-item refund model (docs/components/01 §4.1-4.3): the order has no stored
refund status; each order_item carries its own delivered_at / return window /
final-sale flag, and is the unit of refund eligibility.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin

LOYALTY_TIERS = ("standard", "gold", "vip")
ORDER_STATUSES = ("placed", "shipped", "partially_delivered", "delivered", "cancelled")


class Customer(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    loyalty_tier: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="standard"
    )

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")

    __table_args__ = (
        CheckConstraint(
            "loyalty_tier IN ('standard','gold','vip')",
            name="loyalty_tier_valid",
        ),
    )


class Order(UUIDPKMixin, Base):
    __tablename__ = "orders"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    order_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="placed")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default="USD")
    ordered_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )

    customer: Mapped["Customer"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('placed','shipped','partially_delivered','delivered','cancelled')",
            name="status_valid",
        ),
        CheckConstraint("total_amount >= 0", name="total_amount_nonneg"),
        Index("ix_orders_customer_id", "customer_id"),
    )


class OrderItem(UUIDPKMixin, Base):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    sku: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_final_sale: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    return_window_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="30"
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    order: Mapped["Order"] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0", name="unit_price_nonneg"),
        CheckConstraint("return_window_days >= 0", name="return_window_nonneg"),
        Index("ix_order_items_order_id", "order_id"),
    )
