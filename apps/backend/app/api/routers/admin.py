"""Admin read-only endpoints (docs/components/05 §5). No auth in v1 (known gap)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_conversation_or_404, get_db
from app.models import Conversation
from app.schemas.admin import (
    ConversationList,
    Metrics,
    RefundList,
    TraceResponse,
)
from app.services import admin_service

router = APIRouter(prefix="/admin")


@router.get("/conversations", response_model=ConversationList)
def list_conversations(
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> ConversationList:
    return ConversationList(**admin_service.list_conversations(db, status=status, limit=limit, offset=offset))


@router.get("/conversations/{conversation_id}/trace", response_model=TraceResponse)
def conversation_trace(
    conv: Conversation = Depends(get_conversation_or_404),
    db: Session = Depends(get_db),
) -> TraceResponse:
    return TraceResponse(**admin_service.get_trace(db, conv))


@router.get("/refunds", response_model=RefundList)
def list_refunds(
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> RefundList:
    return RefundList(**admin_service.list_refunds(db, status=status, limit=limit, offset=offset))


@router.get("/metrics", response_model=Metrics)
def metrics(db: Session = Depends(get_db)) -> Metrics:
    return Metrics(**admin_service.metrics(db))
