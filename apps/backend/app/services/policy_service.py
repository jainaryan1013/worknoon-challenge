"""Load policy_rules into a typed PolicyRules object (cached per process) and
read the prose policy document (docs/components/02 §5).

A missing or unparseable rule fails LOUDLY here at load time — never silently
mid-decision. Callers (tools, spec #3) convert a load failure into ESCALATE
(route to a human), never APPROVE (§6 fail-closed).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PolicyDocument, PolicyRule
from app.seed import policy_source
from app.services.rule_engine import PolicyRules

REQUIRED_KEYS = (
    "escalation_threshold_usd",
    "default_return_window_days",
    "final_sale_refundable",
    "dispute_email",
)

_cache: PolicyRules | None = None


class PolicyLoadError(RuntimeError):
    """Raised when policy_rules is missing keys or holds unparseable values."""


def _build(raw: dict[str, object]) -> PolicyRules:
    missing = [k for k in REQUIRED_KEYS if k not in raw]
    if missing:
        raise PolicyLoadError(f"policy_rules missing required key(s): {missing}")
    try:
        return PolicyRules(
            escalation_threshold_usd=Decimal(str(raw["escalation_threshold_usd"])),
            default_return_window_days=int(raw["default_return_window_days"]),  # type: ignore[arg-type]
            final_sale_refundable=bool(raw["final_sale_refundable"]),
            dispute_email=str(raw["dispute_email"]),
        )
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PolicyLoadError(f"policy_rules holds an unparseable value: {exc}") from exc


def from_constants() -> PolicyRules:
    """Canonical PolicyRules built from the single source of truth (no DB).
    Useful for tests and as a fallback equivalence check."""
    return _build({r["key"]: r["value"] for r in policy_source.policy_rules()})


def load_policy_rules(session: Session, *, refresh: bool = False) -> PolicyRules:
    """Load and cache PolicyRules from the DB. Raises PolicyLoadError on
    missing/unparseable rules."""
    global _cache
    if _cache is not None and not refresh:
        return _cache
    rows = session.execute(select(PolicyRule.key, PolicyRule.value)).all()
    _cache = _build({key: value for key, value in rows})
    return _cache


def reset_cache() -> None:
    """Drop the cached rules (used by tests)."""
    global _cache
    _cache = None


def get_policy_document(session: Session) -> str:
    """Latest prose policy document body for the LLM (`get_policy` tool)."""
    body = session.scalar(
        select(PolicyDocument.body_markdown).order_by(PolicyDocument.version.desc())
    )
    if body is None:
        raise PolicyLoadError("no policy_documents row found")
    return body


def get_policy_document_record(session: Session) -> dict:
    """Latest policy document as {version, body_markdown} for the get_policy tool."""
    row = session.execute(
        select(PolicyDocument.version, PolicyDocument.body_markdown).order_by(
            PolicyDocument.version.desc()
        )
    ).first()
    if row is None:
        raise PolicyLoadError("no policy_documents row found")
    return {"version": row.version, "body_markdown": row.body_markdown}
