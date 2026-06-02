"""FastAPI dependencies (docs/components/05 §7.3).

`get_db` is request-scoped and commits on success (used by the non-streaming
endpoints). The chat SSE endpoint deliberately does NOT use it for the stream —
it owns its own session so commit lands after the loop finishes (router-owns-
commit), keeping the row lock across the whole turn.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.llm import get_llm_client
from app.db.session import SessionLocal
from app.models import Conversation
from app.repositories import conversations as conversations_repo


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_settings_dep() -> Settings:
    return get_settings()


def get_llm(settings: Settings = Depends(get_settings_dep)):
    return get_llm_client(settings)


def get_conversation_or_404(
    conversation_id: uuid.UUID, db: Session = Depends(get_db)
) -> Conversation:
    conv = conversations_repo.get(db, conversation_id)
    if conv is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "conversation_not_found", "message": "Conversation not found."},
        )
    return conv
