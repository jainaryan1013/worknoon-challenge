"""OpenAI request-param construction for reasoning vs standard models.

No network: we only test the param builder, which is what avoids the
gpt-5-mini 400 (temperature unsupported; max_tokens -> max_completion_tokens).
"""

from __future__ import annotations

from app.core.llm.openai import OpenAIClient

MESSAGES = [{"role": "user", "content": "hi"}]


def test_reasoning_model_omits_temperature_and_uses_completion_tokens():
    client = OpenAIClient(api_key="x", model="gpt-5-mini", temperature=0.0, max_tokens=2048)
    params = client._build_params(MESSAGES, [])
    assert "temperature" not in params          # gpt-5 rejects any temperature
    assert params["max_completion_tokens"] == 2048
    assert "max_tokens" not in params           # not honored by reasoning models


def test_standard_model_keeps_temperature():
    client = OpenAIClient(api_key="x", model="gpt-4o-mini", temperature=0.0, max_tokens=1024)
    params = client._build_params(MESSAGES, [])
    assert params["temperature"] == 0.0
    assert params["max_completion_tokens"] == 1024


def test_is_reasoning_model_detection():
    assert OpenAIClient._is_reasoning_model("gpt-5-mini")
    assert OpenAIClient._is_reasoning_model("o3-mini")
    assert OpenAIClient._is_reasoning_model("o1")
    assert not OpenAIClient._is_reasoning_model("gpt-4o")
    assert not OpenAIClient._is_reasoning_model("gpt-4.1-mini")
