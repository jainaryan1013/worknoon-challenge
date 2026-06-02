"""Provider-agnostic LLM client interface (docs/components/04 §2).

Each provider normalizes its native streaming format into the common LLMEvent
stream so agent/loop.py never sees provider differences.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol, Union, runtime_checkable


@dataclass
class TextDelta:
    text: str


@dataclass
class ToolCall:
    name: str
    args: dict
    call_id: str


@dataclass
class TurnEnd:
    stop_reason: str


LLMEvent = Union[TextDelta, ToolCall, TurnEnd]


class LLMError(RuntimeError):
    """Raised by a client when the provider call fails (e.g., missing key)."""


@runtime_checkable
class LLMClient(Protocol):
    def stream_turn(
        self, messages: list[dict], tools: list[dict]
    ) -> Iterator[LLMEvent]:
        """Stream one model turn as LLMEvents (text deltas, tool calls, end)."""
        ...

    def format_tools(self, tool_schemas: list[dict]) -> object:
        """Adapt neutral tool schemas to the provider's tool payload."""
        ...


@dataclass
class ScriptedLLMClient:
    """Deterministic client for tests: replays pre-baked LLMEvent batches, one
    batch per stream_turn call (one batch == one model turn)."""

    turns: list[list[LLMEvent]] = field(default_factory=list)
    calls: int = 0

    def stream_turn(self, messages: list[dict], tools: list[dict]) -> Iterator[LLMEvent]:
        if self.calls >= len(self.turns):
            # Model "stops" with no tool calls if the script is exhausted.
            self.calls += 1
            yield TurnEnd("stop")
            return
        batch = self.turns[self.calls]
        self.calls += 1
        yield from batch

    def format_tools(self, tool_schemas: list[dict]) -> object:
        return tool_schemas
