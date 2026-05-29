"""Single source of truth for refund policy.

Both the prose document the LLM reads (`policy_documents`) and the structured
rules the guard enforces (`policy_rules`) are generated from the constants
defined here. Changing a constant changes both outputs, so the text the model
cites and the values the code enforces can never drift (docs/components/01 §5).
"""

from __future__ import annotations

from dataclasses import dataclass

POLICY_VERSION = 1


@dataclass(frozen=True)
class PolicyConstants:
    escalation_threshold_usd: int = 500
    default_return_window_days: int = 30
    final_sale_refundable: bool = False
    dispute_email: str = "disputes@refundagent.example"


CONSTANTS = PolicyConstants()


def policy_rules() -> list[dict]:
    """Structured rows for the policy_rules table (the guard reads these)."""
    return [
        {
            "key": "escalation_threshold_usd",
            "value": CONSTANTS.escalation_threshold_usd,
            "description": (
                "If the projected per-order refund total (prior approved on the "
                "order + current request) is strictly greater than this, escalate."
            ),
        },
        {
            "key": "default_return_window_days",
            "value": CONSTANTS.default_return_window_days,
            "description": "Fallback return window when an item carries none.",
        },
        {
            "key": "final_sale_refundable",
            "value": CONSTANTS.final_sale_refundable,
            "description": "Final-sale items are never refundable.",
        },
        {
            "key": "dispute_email",
            "value": CONSTANTS.dispute_email,
            "description": "Address given on a denial for asynchronous dispute.",
        },
    ]


def policy_document_markdown() -> str:
    """Prose policy for the LLM, generated from the same constants."""
    c = CONSTANTS
    return f"""# Refund Policy (v{POLICY_VERSION})

These rules govern every refund decision. They are enforced in code; the agent
may not override them.

## Eligibility
- **Final-sale items are non-refundable.** (final_sale_refundable = {str(c.final_sale_refundable).lower()})
- An item is refundable only **after it has been delivered** and **within its
  return window**, measured from **that item's own delivery date**.
- The default return window is **{c.default_return_window_days} days** when an
  item does not specify its own.
- Each line item is refundable **independently** of the others on the order, and
  in **whole or partial quantity**.
- An item's **already-refunded units cannot be refunded again**; only the units
  not yet refunded remain eligible.

## Ownership
- A customer may only request refunds on **their own orders**. Requests against
  another customer's order are denied.

## Amounts and escalation
- A refund is processed automatically when the **projected total refunded on the
  order** (everything already approved on that order plus the current request)
  stays **at or below ${c.escalation_threshold_usd}**.
- If that projected total would be **strictly greater than ${c.escalation_threshold_usd}**,
  the request is **escalated to a human** rather than auto-approved.

## Disputes
- A denied request is **final within this chat**. It may be disputed
  asynchronously by emailing **{c.dispute_email}**.
"""
