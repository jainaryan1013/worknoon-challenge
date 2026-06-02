"""Conversation lifecycle endpoints (docs/components/05 §4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_conversation_or_404, get_db
from app.models import Conversation
from app.repositories import conversations as conversations_repo
from app.repositories import customers as customers_repo
from app.repositories import messages as messages_repo
from app.schemas.chat import ConversationCreated, ConversationDetail, MessageOut

router = APIRouter()


@router.post("/conversations", response_model=ConversationCreated, status_code=201)
def create_conversation(db: Session = Depends(get_db)) -> ConversationCreated:
    conv = conversations_repo.create(db)
    return ConversationCreated(
        conversation_id=conv.id, status=conv.status, created_at=conv.created_at
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conv: Conversation = Depends(get_conversation_or_404),
    db: Session = Depends(get_db),
) -> ConversationDetail:
    customer_name = None
    if conv.customer_id is not None:
        customer = customers_repo.get_by_id(db, conv.customer_id)
        customer_name = customer.name if customer else None

    # Customer-facing history only: user + assistant turns (HISTORY_LIMIT -1).
    msgs = messages_repo.history(db, conv.id, limit=-1)
    return ConversationDetail(
        id=conv.id,
        status=conv.status,
        customer_name=customer_name,
        messages=[MessageOut.model_validate(m) for m in msgs],
    )
