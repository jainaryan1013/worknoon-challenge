"""Data access for messages (no business rules)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Message


def add(session: Session, conversation_id: uuid.UUID, role: str, content: str | None) -> Message:
    msg = Message(conversation_id=conversation_id, role=role, content=content)
    session.add(msg)
    session.flush()
    return msg


def history(session: Session, conversation_id: uuid.UUID, limit: int) -> list[Message]:
    """Prior user/assistant messages, oldest-first. limit < 0 = unlimited;
    otherwise the most recent `limit` non-empty messages."""
    rows = list(
        session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role.in_(("user", "assistant")),
                Message.content.isnot(None),
                Message.content != "",
            )
            .order_by(Message.created_at, Message.id)
        )
    )
    if limit is not None and limit >= 0:
        rows = rows[-limit:] if limit > 0 else []
    return rows
