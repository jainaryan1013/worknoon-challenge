"""policy_service: DB load matches the source of truth and fails loudly."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import delete

from app.models import PolicyRule
from app.seed import seed
from app.services import policy_service
from app.services.policy_service import PolicyLoadError


def test_load_matches_constants(db):
    seed.run(db)
    policy_service.reset_cache()
    rules = policy_service.load_policy_rules(db, refresh=True)
    assert rules == policy_service.from_constants()
    assert rules.escalation_threshold_usd == Decimal("500")
    assert rules.final_sale_refundable is False
    assert rules.default_return_window_days == 30


def test_missing_key_fails_loudly(db):
    seed.run(db)
    db.execute(delete(PolicyRule).where(PolicyRule.key == "escalation_threshold_usd"))
    db.flush()
    policy_service.reset_cache()
    with pytest.raises(PolicyLoadError):
        policy_service.load_policy_rules(db, refresh=True)


def test_policy_document_cites_threshold(db):
    seed.run(db)
    body = policy_service.get_policy_document(db)
    assert "$500" in body
    assert policy_service.from_constants().dispute_email in body
