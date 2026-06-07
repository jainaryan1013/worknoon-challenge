"""Conversation tables: conversations, messages, agent_steps.

docs/components/01 §4.5-4.7. conversations.customer_id is nullable — a
conversation exists before identity is verified and is bound on verify_identity.
agent_steps is the reasoning trace; (conversation_id, step_no) is unique and
gapless (§7.4).
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin

CONVERSATION_STATUSES = ("active", "resolved", "escalated")
MESSAGE_ROLES = ("system", "user", "assistant", "tool")
STEP_TYPES = ("model_text", "tool_call", "tool_result", "decision")


class Conversation(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    # Per-conversation capability token (server-minted, returned once at create).
    # Acting on a conversation via /api/chat requires presenting it — this binds
    # the caller to the conversation so a leaked/guessed id alone is not enough.
    session_token: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','resolved','escalated')", name="status_valid"
        ),
        UniqueConstraint("session_token"),
    )


class Message(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "role IN ('system','user','assistant','tool')", name="role_valid"
        ),
        Index("ix_messages_conversation_id", "conversation_id", "created_at"),
    )


class AgentStep(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "agent_steps"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tool_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "type IN ('model_text','tool_call','tool_result','decision')",
            name="type_valid",
        ),
        UniqueConstraint("conversation_id", "step_no", name="conversation_step_no"),
        Index("ix_agent_steps_conversation_id", "conversation_id", "step_no"),
    )
