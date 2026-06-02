"""Data access for agent_steps (no business rules).

step_no is monotonic per conversation (DB unique (conversation_id, step_no));
the per-conversation turn lock in the loop guarantees no interleaving/gaps.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AgentStep


def next_step_no(session: Session, conversation_id: uuid.UUID) -> int:
    current = session.scalar(
        select(func.max(AgentStep.step_no)).where(
            AgentStep.conversation_id == conversation_id
        )
    )
    return (current or 0) + 1


def add(
    session: Session,
    *,
    conversation_id: uuid.UUID,
    step_no: int,
    type: str,
    message_id: uuid.UUID | None = None,
    tool_name: str | None = None,
    tool_input: dict | None = None,
    tool_output: dict | None = None,
    latency_ms: int | None = None,
) -> AgentStep:
    step = AgentStep(
        conversation_id=conversation_id,
        step_no=step_no,
        type=type,
        message_id=message_id,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=tool_output,
        latency_ms=latency_ms,
    )
    session.add(step)
    session.flush()
    return step


def for_conversation(session: Session, conversation_id: uuid.UUID) -> list[AgentStep]:
    return list(
        session.scalars(
            select(AgentStep)
            .where(AgentStep.conversation_id == conversation_id)
            .order_by(AgentStep.step_no)
        )
    )
