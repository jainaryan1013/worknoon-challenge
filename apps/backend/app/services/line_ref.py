"""line_ref: the user-safe handle for an order item (docs/components/03 §2.1, §3.3).

Internal UUIDs never cross the tool boundary. An item is referenced by its
product name, made unique within the order (positional suffix on collision).
The same string is spoken to the customer, passed to the refund tools, and
shown in the admin trace.
"""

from __future__ import annotations

from collections import Counter

from app.models import OrderItem


def build_line_refs(items: list[OrderItem]) -> list[tuple[str, OrderItem]]:
    """Return (line_ref, item) pairs. Deterministic: sorted by (name, sku)."""
    ordered = sorted(items, key=lambda i: (i.product_name, i.sku))
    name_counts = Counter(i.product_name for i in ordered)
    seen: dict[str, int] = {}
    pairs: list[tuple[str, OrderItem]] = []
    for item in ordered:
        name = item.product_name
        if name_counts[name] == 1:
            label = name
        else:
            seen[name] = seen.get(name, 0) + 1
            label = f"{name} ({seen[name]})"
        pairs.append((label, item))
    return pairs


def label_for(items: list[OrderItem], item: OrderItem) -> str:
    for label, candidate in build_line_refs(items):
        if candidate.id == item.id:
            return label
    return item.product_name  # unreachable in practice


def resolve(items: list[OrderItem], line_ref: str) -> list[OrderItem]:
    """All items whose label matches `line_ref` (0, 1, or — guarded — more)."""
    target = line_ref.strip()
    return [item for label, item in build_line_refs(items) if label == target]
