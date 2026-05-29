"""Application settings, loaded from environment / .env.

See docs/components/04 §2 and 07 §6 for the authoritative variable list.
All config is centralized here so the rest of the app never reads os.environ.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Database ---
    # Synchronous psycopg v3 driver. Overridden per-environment: compose points
    # this at the `db` service; the test runner points it at `db-test`.
    database_url: str = "postgresql+psycopg://refund:refund@db:5432/refund"

    # --- LLM provider ---
    llm_provider: Literal["openai", "anthropic"] = "openai"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    llm_model: str | None = None
    llm_temperature: float = 0.0
    llm_max_tokens: int = 1024

    # --- Agent loop ---
    max_agent_iterations: int = 8
    history_limit: int = -1  # prior messages per turn; -1 = unlimited

    # --- Lifecycle / infra ---
    seed_enabled: bool = True
    frontend_origin: str = "http://localhost:8080"

    @property
    def llm_configured(self) -> bool:
        """Whether a usable API key is present for the selected provider."""
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> "Settings":
    """Cached singleton. Use this everywhere instead of constructing Settings()."""
    return Settings()
