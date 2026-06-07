"""Backend API tests (docs/components/05 §9) with FastAPI TestClient.

These endpoints use the app's real (committing) SessionLocal, so the fixture
seeds committed data and TRUNCATEs afterwards to keep the shared schema clean.
The LLM is injected via dependency override — never a live call.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api import deps
from app.api.routers import health as health_router
from app.core.config import Settings
from app.core.llm.base import LLMError, ScriptedLLMClient, TextDelta, ToolCall, TurnEnd
from app.db.session import SessionLocal, engine
from app.main import create_app
from app.seed import seed

_TABLES = "refunds, agent_steps, messages, order_items, orders, conversations, customers, policy_rules, policy_documents"


@pytest.fixture()
def client():
    with SessionLocal() as s:
        seed.run(s)
        s.commit()
    app = create_app()
    tc = TestClient(app, raise_server_exceptions=False)
    try:
        yield tc, app
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {_TABLES} RESTART IDENTITY CASCADE"))


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        if not block.strip():
            continue
        etype = data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                etype = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
        events.append((etype, data))
    return events


def _new_conversation(tc) -> tuple[str, str]:
    r = tc.post("/api/conversations")
    assert r.status_code == 201
    body = r.json()
    return body["conversation_id"], body["session_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- health -----------------------------------------------------------------

def test_health_ok_reports_llm_not_configured_by_default(client):
    tc, _ = client
    r = tc.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["db"] == "ok"
    assert body["llm_configured"] is False


def test_health_llm_configured_true_when_key_present(client):
    tc, app = client
    app.dependency_overrides[deps.get_settings_dep] = lambda: Settings(openai_api_key="sk-x")
    r = tc.get("/api/health")
    assert r.json()["llm_configured"] is True


def test_health_503_when_db_down(client, monkeypatch):
    tc, _ = client

    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(health_router, "SessionLocal", boom)
    r = tc.get("/api/health")
    assert r.status_code == 503
    assert r.json()["db"] == "down"


# --- conversations ----------------------------------------------------------

def test_create_and_fetch_conversation_unverified(client):
    tc, _ = client
    conv_id, _token = _new_conversation(tc)
    r = tc.get(f"/api/conversations/{conv_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "active"
    assert body["customer_name"] is None  # not verified yet
    assert body["messages"] == []
    assert "session_token" not in body  # token is never echoed by read endpoints


def test_unknown_conversation_returns_error_envelope(client):
    tc, _ = client
    r = tc.get("/api/conversations/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "conversation_not_found"


def test_chat_invalid_body_is_422_envelope(client):
    tc, _ = client
    r = tc.post("/api/chat", json={"conversation_id": "not-a-uuid", "message": ""})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_chat_unknown_conversation_404_before_stream(client):
    tc, _ = client
    r = tc.post(
        "/api/chat",
        json={"conversation_id": "00000000-0000-0000-0000-000000000000", "message": "hi"},
        headers=_auth("any-token"),
    )
    assert r.status_code == 404


def test_chat_wrong_token_is_404(client):
    tc, _ = client
    conv_id, _token = _new_conversation(tc)
    r = tc.post(
        "/api/chat",
        json={"conversation_id": conv_id, "message": "hi"},
        headers=_auth("not-the-real-token"),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "conversation_not_found"


def test_chat_missing_token_is_404(client):
    tc, _ = client
    conv_id, _token = _new_conversation(tc)
    r = tc.post("/api/chat", json={"conversation_id": conv_id, "message": "hi"})
    assert r.status_code == 404


# --- chat SSE ---------------------------------------------------------------

def _scripted_refund_client():
    return ScriptedLLMClient(turns=[
        [ToolCall("verify_identity", {"order_number": "ORD-1001", "email": "ada@example.com"}, "c1"), TurnEnd("tool_calls")],
        [ToolCall("process_refund", {"order_number": "ORD-1001", "line_ref": "Wireless Mouse", "quantity": 1}, "c2"), TurnEnd("tool_calls")],
        [TextDelta("Your refund is approved."), TurnEnd("stop")],
    ])


def test_chat_streams_sse_frames_and_decision(client):
    tc, app = client
    app.dependency_overrides[deps.get_llm] = _scripted_refund_client
    conv_id, token = _new_conversation(tc)

    r = tc.post(
        "/api/chat",
        json={"conversation_id": conv_id, "message": "refund my mouse"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")

    events = parse_sse(r.text)
    types = [t for t, _ in events]
    assert "tool_call" in types and "tool_result" in types
    assert types[-1] == "done"
    decision = next(d for t, d in events if t == "decision")
    assert decision["outcome"] == "APPROVE"
    assert decision["amount"] == "120.00"


def test_chat_midstream_failure_is_sse_error_not_http_error(client):
    tc, app = client

    class BrokenClient:
        def stream_turn(self, messages, tools):
            raise LLMError("no key")
            yield  # pragma: no cover

        def format_tools(self, schemas):
            return schemas

    app.dependency_overrides[deps.get_llm] = lambda: BrokenClient()
    conv_id, token = _new_conversation(tc)
    r = tc.post(
        "/api/chat",
        json={"conversation_id": conv_id, "message": "hi"},
        headers=_auth(token),
    )
    assert r.status_code == 200  # status line already sent; error is in-band
    types = [t for t, _ in parse_sse(r.text)]
    assert "error" in types and types[-1] == "done"


# --- admin ------------------------------------------------------------------

def test_admin_refunds_and_metrics(client):
    tc, _ = client
    r = tc.get("/api/admin/refunds")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 4  # seed has 4 approved refunds
    assert all("order_number" in item and "item" in item for item in body["items"])

    m = tc.get("/api/admin/metrics").json()
    assert m["approved"] >= 4
    assert 0.0 <= m["approval_rate"] <= 1.0


def test_admin_trace_after_chat(client):
    tc, app = client
    app.dependency_overrides[deps.get_llm] = _scripted_refund_client
    conv_id, token = _new_conversation(tc)
    tc.post(
        "/api/chat",
        json={"conversation_id": conv_id, "message": "refund mouse"},
        headers=_auth(token),
    )

    r = tc.get(f"/api/admin/conversations/{conv_id}/trace")
    assert r.status_code == 200
    body = r.json()
    step_types = [s["type"] for s in body["steps"]]
    assert "tool_call" in step_types and "decision" in step_types
    assert body["conversation"]["customer_name"] == "Ada Lovelace"


def test_admin_conversations_list_pagination(client):
    tc, _ = client
    _new_conversation(tc)
    r = tc.get("/api/admin/conversations?limit=10&offset=0")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert len(body["items"]) <= 10
