"""OpenAIClient (default provider) — normalizes tool-call deltas to LLMEvent.

The SDK is imported lazily so the app boots without a key; the first
stream_turn call surfaces a clean LLMError instead of crashing (§2).
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from app.core.llm.base import LLMError, LLMEvent, TextDelta, ToolCall, TurnEnd

_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIClient:
    def __init__(
        self, api_key: str | None, model: str | None, temperature: float, max_tokens: int
    ):
        self._api_key = api_key
        self._model = model or _DEFAULT_MODEL
        self._temperature = temperature
        self._max_tokens = max_tokens

    def format_tools(self, tool_schemas: list[dict]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                },
            }
            for t in tool_schemas
        ]

    @staticmethod
    def _to_openai_messages(messages: list[dict]) -> list[dict]:
        out: list[dict] = []
        for m in messages:
            role = m["role"]
            if role == "assistant" and m.get("tool_calls"):
                out.append(
                    {
                        "role": "assistant",
                        "content": m.get("content") or None,
                        "tool_calls": [
                            {
                                "id": c["call_id"],
                                "type": "function",
                                "function": {
                                    "name": c["name"],
                                    "arguments": json.dumps(c["args"]),
                                },
                            }
                            for c in m["tool_calls"]
                        ],
                    }
                )
            elif role == "tool":
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": m["tool_call_id"],
                        "content": m["content"],
                    }
                )
            else:
                out.append({"role": role, "content": m.get("content", "")})
        return out

    @staticmethod
    def _is_reasoning_model(model: str) -> bool:
        """gpt-5 family and o-series are reasoning models: they reject
        `temperature` (only the default is allowed) and require
        `max_completion_tokens` instead of `max_tokens`."""
        m = model.lower()
        return m.startswith(("gpt-5", "o1", "o3", "o4"))

    def _build_params(self, messages: list[dict], tools: list[dict]) -> dict:
        params: dict = {
            "model": self._model,
            "messages": self._to_openai_messages(messages),
            "tools": self.format_tools(tools) or None,
            # max_completion_tokens is accepted by current chat models and is the
            # only token cap reasoning models honor.
            "max_completion_tokens": self._max_tokens,
        }
        # Reasoning models only allow the default temperature; sending any value
        # (even 0) returns 400. Omit it for them.
        if not self._is_reasoning_model(self._model):
            params["temperature"] = self._temperature
        return params

    def stream_turn(self, messages: list[dict], tools: list[dict]) -> Iterator[LLMEvent]:
        if not self._api_key:
            raise LLMError("OpenAI API key is not configured.")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise LLMError("openai package is not installed.") from exc

        client = OpenAI(api_key=self._api_key)
        try:
            stream = client.chat.completions.create(
                **self._build_params(messages, tools), stream=True
            )
        except Exception as exc:  # noqa: BLE001 - normalize all provider errors
            raise LLMError(str(exc)) from exc

        partial: dict[int, dict] = {}
        finish = "stop"
        for chunk in stream:
            choice = chunk.choices[0]
            delta = choice.delta
            if delta.content:
                yield TextDelta(delta.content)
            for tc in delta.tool_calls or []:
                slot = partial.setdefault(tc.index, {"id": None, "name": "", "args": ""})
                if tc.id:
                    slot["id"] = tc.id
                if tc.function and tc.function.name:
                    slot["name"] = tc.function.name
                if tc.function and tc.function.arguments:
                    slot["args"] += tc.function.arguments
            if choice.finish_reason:
                finish = choice.finish_reason

        for slot in partial.values():
            try:
                args = json.loads(slot["args"]) if slot["args"] else {}
            except json.JSONDecodeError:
                args = {}
            yield ToolCall(name=slot["name"], args=args, call_id=slot["id"] or slot["name"])
        yield TurnEnd(finish)
