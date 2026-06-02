"""Bridge from the tools registry (#3) to LLM-facing JSON schemas + dispatch.

The agent loop asks for `tool_schemas()` to advertise tools to the model, and
calls `dispatch()` to run a chosen tool through the validated tool boundary.
"""

from __future__ import annotations

from app.schemas.tools import ToolResult
from app.tools import REGISTRY
from app.tools.context import ToolContext


def tool_schemas() -> list[dict]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.input_model.model_json_schema(),
        }
        for spec in REGISTRY.values()
    ]


def dispatch(name: str, args: dict, ctx: ToolContext) -> ToolResult:
    spec = REGISTRY.get(name)
    if spec is None:
        return ToolResult.fail("unknown_tool", f"Unknown tool: {name}")
    try:
        return spec.fn(ctx, args or {})
    except Exception:  # noqa: BLE001 - tools shouldn't raise; surface a safe error
        return ToolResult.fail("tool_error", "Something went wrong handling that request.")
