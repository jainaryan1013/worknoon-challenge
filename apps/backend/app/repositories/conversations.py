"""Data access for conversations (no business rules)."""

from __future__ import annotations

import secrets
import uuid

from sqlalchemy.orm import Session

from app.models import Conversation


def get(session: Session, conversation_id: uuid.UUID) -> Conversation | None:
    return session.get(Conversation, conversation_id)


def get_for_session(
    session: Session, conversation_id: uuid.UUID, token: str | None
) -> Conversation | None:
    """Return the conversation only if `token` matches its session_token
    (constant-time). Used to authorize /api/chat; mismatch/missing → None."""
    if not token:
        return None
    conv = session.get(Conversation, conversation_id)
    if conv is None:
        return None
    if not secrets.compare_digest(conv.session_token, token):
        return None
    return conv


def create(session: Session) -> Conversation:
    conv = Conversation(status="active", session_token=secrets.token_urlsafe(32))
    session.add(conv)
    session.flush()
    return conv


def bind_customer(session: Session, conv: Conversation, customer_id: uuid.UUID) -> None:
    conv.customer_id = customer_id
    session.flush()


def set_status(session: Session, conv: Conversation, status: str) -> None:
    conv.status = status
    session.flush()
