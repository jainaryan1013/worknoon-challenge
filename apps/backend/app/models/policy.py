"""Dual policy store: policy_documents (prose for the LLM) and policy_rules
(structured for the guard). docs/components/01 §4.8-4.9, §5.

Both tables are seeded from one source (seed/policy_source.py) so the text the
model cites and the values the code enforces can never drift.
"""

from __future__ import annotations

from sqlalchemy import Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class PolicyDocument(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "policy_documents"

    version: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)


class PolicyRule(UUIDPKMixin, Base):
    __tablename__ = "policy_rules"

    key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    value: Mapped[dict | list | int | str | bool] = mapped_column(
        JSONB, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
