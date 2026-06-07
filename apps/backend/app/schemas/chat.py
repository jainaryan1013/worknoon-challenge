"""Chat + conversation request/response schemas (docs/components/05 §3, §4).

Only human-safe identifiers appear here: conversation_id, order_number, and
product-name line_refs. Internal UUIDs never surface.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SelectionItem(BaseModel):
    line_ref: str
    # Bounded at the API channel so a crafted selection can't drive unbounded
    # work; the tool-layer RefundInput stays unbounded on purpose (invalid qty
    # there is a NEEDS_INFO verdict, not a request rejection).
    quantity: int = Field(ge=1, le=100)


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID
    message: str = Field(min_length=1, max_length=4000)
    # Cap the selection length: one process_refund runs per item, so an
    # unbounded list is a DoS lever. 20 covers any realistic multi-item order.
    selection: list[SelectionItem] | None = Field(default=None, max_length=20)


class ConversationCreated(BaseModel):
    conversation_id: uuid.UUID
    status: str
    created_at: datetime
    # Capability token for this conversation. Returned ONLY here; the client must
    # send it as `Authorization: Bearer <token>` on /api/chat. Never echoed by
    # any read endpoint, the SSE stream, or the admin trace.
    session_token: str


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    content: str | None
    created_at: datetime


class ConversationDetail(BaseModel):
    id: uuid.UUID
    status: str
    customer_name: str | None
    messages: list[MessageOut]
