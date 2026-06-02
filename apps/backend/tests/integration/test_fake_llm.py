"""The fake LLM provider drives the real stack to deterministic outcomes.

These prove the scaffolding the Playwright E2E relies on: the canonical flows
resolve through the real tools + rule engine, not a stubbed decision.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.agent import loop
from app.core.llm.fake import FakeLLMClient
from app.models import Refund
from app.repositories import conversations as conversations_repo
from app.seed import seed


def _conv(db):
    return conversations_repo.create(db).id


def _approved(db, conv_id):
    return db.scalar(
        select(func.count())
        .select_from(Refund)
        .where(Refund.conversation_id == conv_id, Refund.status == "approved")
    )


def test_fake_verify_then_refund_one_message(db):
    seed.run(db)
    conv_id = _conv(db)
    out = list(
        loop.run_turn(
            db,
            FakeLLMClient(),
            conv_id,
            "Verify ORD-1001 ada@example.com and refund my Wireless Mouse",
        )
    )
    decisions = [e for e in out if e.type == "decision"]
    assert decisions and decisions[-1].data["outcome"] == "APPROVE"
    assert _approved(db, conv_id) == 1


def test_fake_return_flow_emits_selector_then_refunds_selection(db):
    seed.run(db)
    conv_id = _conv(db)

    first = list(
        loop.run_turn(
            db,
            FakeLLMClient(),
            conv_id,
            "Verify ORD-1001 ada@example.com — I want to return an item",
        )
    )
    assert any(e.type == "return_selector" for e in first)

    second = list(
        loop.run_turn(
            db,
            FakeLLMClient(),
            conv_id,
            "Return 1 × Wireless Mouse — ORD-1001",
            selection=[{"line_ref": "Wireless Mouse", "quantity": 1}],
        )
    )
    decisions = [e for e in second if e.type == "decision"]
    assert decisions and decisions[-1].data["outcome"] == "APPROVE"
    assert _approved(db, conv_id) == 1
