"""Admin read-model schemas (docs/components/05 §5). Internal-staff view, but
still human-safe: order numbers + product names + line_refs, never UUIDs of
items/customers.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ConversationListItem(BaseModel):
    id: uuid.UUID
    customer_name: str | None
    status: str
    last_decision: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationList(BaseModel):
    items: list[ConversationListItem]
    total: int


class TraceConversation(BaseModel):
    id: uuid.UUID
    status: str
    customer_name: str | None
    created_at: datetime


class TraceMessage(BaseModel):
    role: str
    content: str | None
    created_at: datetime


class TraceStep(BaseModel):
    step_no: int
    type: str
    tool_name: str | None
    tool_input: Any | None
    tool_output: Any | None
    latency_ms: int | None
    created_at: datetime


class TraceResponse(BaseModel):
    conversation: TraceConversation
    messages: list[TraceMessage]
    steps: list[TraceStep]


class RefundOut(BaseModel):
    order_number: str
    item: str
    quantity: int
    amount: str
    status: str
    reason_code: str
    reason: str | None
    decided_by: str
    created_at: datetime


class RefundList(BaseModel):
    items: list[RefundOut]
    total: int


class Metrics(BaseModel):
    approved: int
    denied: int
    escalated: int
    needs_info: int
    total: int
    approval_rate: float
    escalation_rate: float
