"""Data access for conversations (no business rules)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models import Conversation


def get(session: Session, conversation_id: uuid.UUID) -> Conversation | None:
    return session.get(Conversation, conversation_id)


def create(session: Session) -> Conversation:
    conv = Conversation(status="active")
    session.add(conv)
    session.flush()
    return conv


def bind_customer(session: Session, conv: Conversation, customer_id: uuid.UUID) -> None:
    conv.customer_id = customer_id
    session.flush()


def set_status(session: Session, conv: Conversation, status: str) -> None:
    conv.status = status
    session.flush()
