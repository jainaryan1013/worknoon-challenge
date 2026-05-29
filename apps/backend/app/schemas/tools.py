"""Tool I/O schemas + the common result envelope (docs/components/03 §3, §6).

These Pydantic models are the contract the LLM sees (spec #4 builds JSON tool
schemas from them) and the validation boundary before any DB access.

Note on `extra="ignore"`: the model may emit stray fields like `amount` or
`approved`. We silently drop them — they are NOT parameters, so they can never
influence a decision (enforcement matrix §5).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _ToolInput(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class VerifyIdentityInput(_ToolInput):
    order_number: str
    email: str


class EmptyInput(_ToolInput):
    pass


class OrderRefInput(_ToolInput):
    order_number: str


class RefundInput(_ToolInput):
    order_number: str
    line_ref: str
    # No ge=1 constraint on purpose: an invalid quantity is a NEEDS_INFO verdict
    # from the rule engine (§3.5/§3.6), not an input-validation rejection.
    quantity: int


class EscalateInput(_ToolInput):
    order_number: str
    line_ref: str | None = None
    summary: str = ""


class ToolError(BaseModel):
    code: str
    message: str


class ToolResult(BaseModel):
    ok: bool
    data: Any | None = None
    error: ToolError | None = None

    @classmethod
    def success(cls, data: Any) -> "ToolResult":
        return cls(ok=True, data=data)

    @classmethod
    def fail(cls, code: str, message: str) -> "ToolResult":
        return cls(ok=False, error=ToolError(code=code, message=message))
