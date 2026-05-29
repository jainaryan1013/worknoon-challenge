"""Idempotent seeding (docs/components/01 §6, 07 §3).

Writes the dual policy store and the fixture matrix. Idempotent: if any
customers already exist it is a no-op, so a container restart re-runs the
entrypoint without duplicating data. Gated by SEED_ENABLED at the entrypoint.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    Customer,
    Order,
    OrderItem,
    PolicyDocument,
    PolicyRule,
    Refund,
)
from app.seed import fixtures, policy_source

log = logging.getLogger(__name__)


def _days_ago(n: int | None) -> datetime | None:
    if n is None:
        return None
    return datetime.now(timezone.utc) - timedelta(days=n)


def _seed_policy(session: Session) -> None:
    session.add(
        PolicyDocument(
            version=policy_source.POLICY_VERSION,
            body_markdown=policy_source.policy_document_markdown(),
        )
    )
    for rule in policy_source.policy_rules():
        session.add(
            PolicyRule(
                key=rule["key"], value=rule["value"], description=rule["description"]
            )
        )


def _seed_customers(session: Session) -> None:
    for cust_spec in fixtures.all_customers():
        customer = Customer(
            name=cust_spec["name"],
            email=cust_spec["email"],
            loyalty_tier=cust_spec["loyalty_tier"],
        )
        session.add(customer)
        session.flush()  # assign customer.id

        for order_spec in cust_spec["orders"]:
            items = order_spec["items"]
            total = sum(
                (Decimal(it["unit_price"]) * it["quantity"] for it in items),
                Decimal("0.00"),
            )
            order = Order(
                customer_id=customer.id,
                order_number=order_spec["order_number"],
                status=order_spec["status"],
                total_amount=total,
                currency="USD",
                ordered_at=_days_ago(order_spec["ordered_days_ago"]),
            )
            session.add(order)
            session.flush()  # assign order.id

            for it in items:
                unit_price = Decimal(it["unit_price"])
                item = OrderItem(
                    order_id=order.id,
                    product_name=it["product_name"],
                    sku=it["sku"],
                    category=it["category"],
                    quantity=it["quantity"],
                    unit_price=unit_price,
                    is_final_sale=it["is_final_sale"],
                    return_window_days=it["return_window_days"],
                    delivered_at=_days_ago(it["delivered_days_ago"]),
                )
                session.add(item)
                session.flush()  # assign item.id

                for ref in it["refunds"]:
                    session.add(
                        Refund(
                            order_id=order.id,
                            order_item_id=item.id,
                            customer_id=customer.id,
                            conversation_id=None,
                            quantity=ref["quantity"],
                            amount=unit_price * ref["quantity"],
                            status=ref["status"],
                            reason_code=ref["reason_code"],
                            reason=ref.get("reason"),
                            policy_refs=[],
                            decided_by=ref["decided_by"],
                        )
                    )


def run(session: Session) -> bool:
    """Seed within the given session. Returns False if skipped (already seeded).

    Does not commit — the caller owns the transaction boundary.
    """
    already = session.scalar(select(Customer.id).limit(1))
    if already is not None:
        log.info("seed: customers already present, skipping")
        return False
    _seed_policy(session)
    _seed_customers(session)
    log.info("seed: inserted policy + fixtures")
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as session:
        seeded = run(session)
        session.commit()
    print("seeded" if seeded else "skipped (already seeded)")


if __name__ == "__main__":
    main()
