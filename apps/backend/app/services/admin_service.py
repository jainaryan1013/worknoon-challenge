"""Read-only aggregation for the admin dashboard (docs/components/05 §5).

Thin read logic over repositories/queries — no business rules, no writes.
Output stays human-safe: order numbers + product names, never internal UUIDs.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AgentStep, Conversation, Customer, Message, Order, OrderItem, Refund


def _customer_name(db: Session, customer_id: uuid.UUID | None) -> str | None:
    if customer_id is None:
        return None
    return db.scalar(select(Customer.name).where(Customer.id == customer_id))


def _message_count(db: Session, conversation_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.role.in_(("user", "assistant")),
        )
    )


def _last_activity(db: Session, conv: Conversation):
    last_msg = db.scalar(
        select(func.max(Message.created_at)).where(
            Message.conversation_id == conv.id
        )
    )
    return last_msg or conv.created_at


def _last_decision(db: Session, conversation_id: uuid.UUID) -> str | None:
    return db.scalar(
        select(Refund.status)
        .where(Refund.conversation_id == conversation_id)
        .order_by(Refund.created_at.desc())
        .limit(1)
    )


def list_conversations(
    db: Session, *, status: str | None, limit: int, offset: int
) -> dict:
    base = select(Conversation)
    count_q = select(func.count()).select_from(Conversation)
    if status:
        base = base.where(Conversation.status == status)
        count_q = count_q.where(Conversation.status == status)
    total = db.scalar(count_q)
    rows = list(
        db.scalars(
            base.order_by(Conversation.created_at.desc()).limit(limit).offset(offset)
        )
    )
    items = [
        {
            "id": c.id,
            "customer_name": _customer_name(db, c.customer_id),
            "status": c.status,
            "last_decision": _last_decision(db, c.id),
            "message_count": _message_count(db, c.id),
            "created_at": c.created_at,
            "updated_at": _last_activity(db, c),
        }
        for c in rows
    ]
    return {"items": items, "total": total}


def get_trace(db: Session, conv: Conversation) -> dict:
    messages = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at, Message.id)
        )
    )
    steps = list(
        db.scalars(
            select(AgentStep)
            .where(AgentStep.conversation_id == conv.id)
            .order_by(AgentStep.step_no)
        )
    )
    return {
        "conversation": {
            "id": conv.id,
            "status": conv.status,
            "customer_name": _customer_name(db, conv.customer_id),
            "created_at": conv.created_at,
        },
        "messages": [
            {"role": m.role, "content": m.content, "created_at": m.created_at}
            for m in messages
        ],
        "steps": [
            {
                "step_no": s.step_no,
                "type": s.type,
                "tool_name": s.tool_name,
                "tool_input": s.tool_input,
                "tool_output": s.tool_output,
                "latency_ms": s.latency_ms,
                "created_at": s.created_at,
            }
            for s in steps
        ],
    }


def list_refunds(db: Session, *, status: str | None, limit: int, offset: int) -> dict:
    base = (
        select(Refund, Order.order_number, OrderItem.product_name)
        .join(Order, Refund.order_id == Order.id)
        .join(OrderItem, Refund.order_item_id == OrderItem.id)
    )
    count_q = select(func.count()).select_from(Refund)
    if status:
        base = base.where(Refund.status == status)
        count_q = count_q.where(Refund.status == status)
    total = db.scalar(count_q)
    rows = db.execute(
        base.order_by(Refund.created_at.desc()).limit(limit).offset(offset)
    ).all()
    items = [
        {
            "order_number": order_number,
            "item": product_name,
            "quantity": r.quantity,
            "amount": str(r.amount),
            "status": r.status,
            "reason_code": r.reason_code,
            "reason": r.reason,
            "decided_by": r.decided_by,
            "created_at": r.created_at,
        }
        for r, order_number, product_name in rows
    ]
    return {"items": items, "total": total}


def metrics(db: Session) -> dict:
    by_status = dict(
        db.execute(
            select(Refund.status, func.count()).group_by(Refund.status)
        ).all()
    )
    approved = by_status.get("approved", 0)
    denied = by_status.get("denied", 0)
    escalated = by_status.get("escalated", 0)
    needs_info = db.scalar(
        select(func.count())
        .select_from(AgentStep)
        .where(
            AgentStep.type == "tool_result",
            AgentStep.tool_name == "process_refund",
            AgentStep.tool_output["data"]["outcome"].astext == "NEEDS_INFO",
        )
    )
    total = approved + denied + escalated
    return {
        "approved": approved,
        "denied": denied,
        "escalated": escalated,
        "needs_info": needs_info or 0,
        "total": total,
        "approval_rate": round(approved / total, 4) if total else 0.0,
        "escalation_rate": round(escalated / total, 4) if total else 0.0,
    }
