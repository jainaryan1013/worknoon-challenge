"""AnthropicClient (alternate provider) — normalizes content blocks to LLMEvent.

Lazy SDK import; the first stream_turn surfaces a clean LLMError without a key.
Anthropic takes the system prompt as a separate parameter, so it's split out of
the neutral message list here.
"""

from __future__ import annotations

from collections.abc import Iterator

from app.core.llm.base import LLMError, LLMEvent, TextDelta, ToolCall, TurnEnd

_DEFAULT_MODEL = "claude-sonnet-4-6"


class AnthropicClient:
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
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["parameters"],
            }
            for t in tool_schemas
        ]

    @staticmethod
    def _split(messages: list[dict]) -> tuple[str, list[dict]]:
        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        out: list[dict] = []
        for m in messages:
            role = m["role"]
            if role == "system":
                continue
            if role == "assistant" and m.get("tool_calls"):
                blocks = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for c in m["tool_calls"]:
                    blocks.append(
                        {"type": "tool_use", "id": c["call_id"], "name": c["name"], "input": c["args"]}
                    )
                out.append({"role": "assistant", "content": blocks})
            elif role == "tool":
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m["tool_call_id"],
                                "content": m["content"],
                            }
                        ],
                    }
                )
            else:
                out.append({"role": role, "content": m.get("content", "")})
        return "\n\n".join(system_parts), out

    def stream_turn(self, messages: list[dict], tools: list[dict]) -> Iterator[LLMEvent]:
        if not self._api_key:
            raise LLMError("Anthropic API key is not configured.")
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise LLMError("anthropic package is not installed.") from exc

        system, conv = self._split(messages)
        client = anthropic.Anthropic(api_key=self._api_key)
        tool_calls: list[ToolCall] = []
        finish = "stop"
        try:
            with client.messages.stream(
                model=self._model,
                system=system,
                messages=conv,
                tools=self.format_tools(tools),
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            ) as stream:
                for text in stream.text_stream:
                    if text:
                        yield TextDelta(text)
                final = stream.get_final_message()
        except Exception as exc:  # noqa: BLE001 - normalize all provider errors
            raise LLMError(str(exc)) from exc

        for block in final.content:
            if getattr(block, "type", None) == "tool_use":
                tool_calls.append(ToolCall(name=block.name, args=dict(block.input), call_id=block.id))
        finish = final.stop_reason or "stop"
        for tc in tool_calls:
            yield tc
        yield TurnEnd(finish)
