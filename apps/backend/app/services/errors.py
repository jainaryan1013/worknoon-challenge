"""Domain errors raised by services and mapped to ToolResult by the tools."""

from __future__ import annotations


class ServiceError(Exception):
    """Carries a user-safe code + message (no internals)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
