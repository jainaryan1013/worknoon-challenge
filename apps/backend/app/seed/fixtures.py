"""Deterministic fixture matrix for seeding (docs/components/01 §6).

15 customers: 8 carrying the named adversarial scenarios + 7 plain fillers.
Dates are expressed as "days ago" and resolved to absolute UTC timestamps at
seed time, so age-based scenarios stay valid whenever the demo runs.

Each refund listed here is a *pre-existing* approved refund used to set up
already-consumed quantity (partial / fully refunded) and per-order refund totals
(boundary / over-threshold). reason_code/decided_by mark them as historical.
"""

from __future__ import annotations

from typing import Any

# Reusable refund-window default mirrors policy default; per-item override allowed.
_W = 30


def _item(
    product_name: str,
    sku: str,
    unit_price: str,
    quantity: int = 1,
    *,
    category: str | None = "general",
    is_final_sale: bool = False,
    return_window_days: int = _W,
    delivered_days_ago: int | None = 5,
    refunds: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "product_name": product_name,
        "sku": sku,
        "unit_price": unit_price,
        "quantity": quantity,
        "category": category,
        "is_final_sale": is_final_sale,
        "return_window_days": return_window_days,
        "delivered_days_ago": delivered_days_ago,
        "refunds": refunds or [],
    }


def _refund(quantity: int, reason_code: str = "seed_historical") -> dict[str, Any]:
    """A pre-existing APPROVED refund (amount is computed from the item at seed)."""
    return {
        "quantity": quantity,
        "status": "approved",
        "reason_code": reason_code,
        "reason": "Seeded historical refund.",
        "decided_by": "agent",
    }


# --- 8 named fixtures -------------------------------------------------------

NAMED_CUSTOMERS: list[dict[str, Any]] = [
    {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "loyalty_tier": "gold",
        "orders": [
            {  # Happy item + Partial-quantity line (1 of 3 already refunded)
                "order_number": "ORD-1001",
                "status": "delivered",
                "ordered_days_ago": 10,
                "items": [
                    _item("Wireless Mouse", "SKU-MOUSE", "120.00",
                          delivered_days_ago=5),
                    _item("Mechanical Keyboard", "SKU-KEYB", "60.00", quantity=3,
                          delivered_days_ago=6, refunds=[_refund(1)]),
                ],
            }
        ],
    },
    {
        "name": "Ben Franklin",
        "email": "ben@example.com",
        "loyalty_tier": "standard",
        "orders": [
            {  # Final-sale item alongside a refundable sibling
                "order_number": "ORD-1002",
                "status": "delivered",
                "ordered_days_ago": 12,
                "items": [
                    _item("Clearance Tee", "SKU-TEE", "80.00",
                          is_final_sale=True, delivered_days_ago=4),
                    _item("Water Bottle", "SKU-BOTL", "50.00",
                          delivered_days_ago=4),
                ],
            }
        ],
    },
    {
        "name": "Cara Diaz",
        "email": "cara@example.com",
        "loyalty_tier": "standard",
        "orders": [
            {  # Window-expired: delivered 60d ago, 30-day window
                "order_number": "ORD-1003",
                "status": "delivered",
                "ordered_days_ago": 65,
                "items": [
                    _item("Desk Lamp", "SKU-LAMP", "90.00",
                          return_window_days=30, delivered_days_ago=60),
                ],
            }
        ],
    },
    {
        "name": "Dan Brown",
        "email": "dan@example.com",
        "loyalty_tier": "standard",
        "orders": [
            {  # Undelivered: shipped, delivered_at NULL
                "order_number": "ORD-1004",
                "status": "shipped",
                "ordered_days_ago": 3,
                "items": [
                    _item("Standing Fan", "SKU-FAN", "70.00",
                          delivered_days_ago=None),
                ],
            }
        ],
    },
    {
        "name": "Eve Adams",
        "email": "eve@example.com",
        "loyalty_tier": "vip",
        "orders": [
            {  # Mixed delivery: A delivered, B not yet
                "order_number": "ORD-1005",
                "status": "partially_delivered",
                "ordered_days_ago": 7,
                "items": [
                    _item("Phone Case", "SKU-CASE", "60.00",
                          delivered_days_ago=2),
                    _item("Screen Protector", "SKU-SCRN", "40.00",
                          delivered_days_ago=None),
                ],
            }
        ],
    },
    {
        "name": "Finn Murphy",
        "email": "finn@example.com",
        "loyalty_tier": "standard",
        "orders": [
            {  # Fully refunded item: qty 2, 2 units already approved
                "order_number": "ORD-1006",
                "status": "delivered",
                "ordered_days_ago": 15,
                "items": [
                    _item("Coffee Mug", "SKU-MUG", "25.00", quantity=2,
                          delivered_days_ago=8, refunds=[_refund(2)]),
                ],
            }
        ],
    },
    {
        "name": "Gina Park",
        "email": "gina@example.com",
        "loyalty_tier": "gold",
        "orders": [
            {  # Boundary: approved refunds total EXACTLY $500.00
                "order_number": "ORD-1007",
                "status": "delivered",
                "ordered_days_ago": 20,
                "items": [
                    _item("Office Chair", "SKU-CHAIR", "250.00", quantity=2,
                          delivered_days_ago=10, refunds=[_refund(2)]),
                ],
            },
            {  # Over-threshold setup: $480 approved + a $60 item still available
                "order_number": "ORD-1008",
                "status": "delivered",
                "ordered_days_ago": 18,
                "items": [
                    _item("Monitor Arm", "SKU-ARM", "160.00", quantity=3,
                          delivered_days_ago=9, refunds=[_refund(3)]),
                    _item("Cable Kit", "SKU-CABL", "60.00",
                          delivered_days_ago=9),
                ],
            },
        ],
    },
    {
        "name": "Hank Green",
        "email": "hank@example.com",
        "loyalty_tier": "standard",
        "orders": [
            {  # Wrong-owner target: another customer will try to refund this
                "order_number": "ORD-1009",
                "status": "delivered",
                "ordered_days_ago": 6,
                "items": [
                    _item("Backpack", "SKU-BAG", "110.00",
                          delivered_days_ago=3),
                ],
            }
        ],
    },
]

# --- 7 plain fillers --------------------------------------------------------

_FILLER_NAMES = [
    ("Ivy Stone", "ivy@example.com"),
    ("Jack Reed", "jack@example.com"),
    ("Kira Blue", "kira@example.com"),
    ("Leo Marsh", "leo@example.com"),
    ("Mona Vale", "mona@example.com"),
    ("Nate Cole", "nate@example.com"),
    ("Omar Vance", "omar@example.com"),
]


def _fillers() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, (name, email) in enumerate(_FILLER_NAMES, start=1010):
        out.append(
            {
                "name": name,
                "email": email,
                "loyalty_tier": "standard",
                "orders": [
                    {
                        "order_number": f"ORD-{i}",
                        "status": "delivered",
                        "ordered_days_ago": 14,
                        "items": [
                            _item(f"Product {i}", f"SKU-{i}", "45.00",
                                  delivered_days_ago=7),
                        ],
                    }
                ],
            }
        )
    return out


def all_customers() -> list[dict[str, Any]]:
    return NAMED_CUSTOMERS + _fillers()
