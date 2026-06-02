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
    quantity: int


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID
    message: str = Field(min_length=1, max_length=4000)
    selection: list[SelectionItem] | None = None


class ConversationCreated(BaseModel):
    conversation_id: uuid.UUID
    status: str
    created_at: datetime


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
