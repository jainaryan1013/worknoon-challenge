"""LLM client factory + re-exported event types (docs/components/04 §2)."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.llm.base import (
    LLMClient,
    LLMError,
    LLMEvent,
    ScriptedLLMClient,
    TextDelta,
    ToolCall,
    TurnEnd,
)


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    settings = settings or get_settings()
    if settings.llm_provider == "fake":
        from app.core.llm.fake import FakeLLMClient

        return FakeLLMClient()
    if settings.llm_provider == "anthropic":
        from app.core.llm.anthropic import AnthropicClient

        return AnthropicClient(
            api_key=settings.anthropic_api_key,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
    from app.core.llm.openai import OpenAIClient

    return OpenAIClient(
        api_key=settings.openai_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )


__all__ = [
    "LLMClient",
    "LLMError",
    "LLMEvent",
    "TextDelta",
    "ToolCall",
    "TurnEnd",
    "ScriptedLLMClient",
    "get_llm_client",
]
