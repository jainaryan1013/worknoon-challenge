"""Data access for customers (no business rules)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Customer


def get_by_id(session: Session, customer_id: uuid.UUID) -> Customer | None:
    return session.get(Customer, customer_id)


def get_by_email(session: Session, email: str) -> Customer | None:
    """Case-insensitive email lookup (identity handle)."""
    return session.scalar(
        select(Customer).where(func.lower(Customer.email) == email.strip().lower())
    )
