"""Application settings loaded from environment / .env.

Access via the cached :func:`get_settings`. In tests, after mutating env vars,
call ``get_settings.cache_clear()`` to pick up the changes.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    # --- Auth ---
    jwt_secret: str = "change-me-please"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # --- LLM (Gemini) ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    # Ordered fallbacks tried on per-day quota / transient errors. Kept to models
    # that respond reliably on the free tier (gemini-flash-latest tends to time
    # out, so it's deliberately not here).
    gemini_fallback_models: str = (
        "gemini-2.0-flash,gemini-2.5-flash,gemini-flash-lite-latest"
    )
    gemini_base_url: str = "https://generativelanguage.googleapis.com"

    # --- Admin ---
    # Comma-separated emails allowed on /api/admin/* (empty = nobody is admin).
    admin_emails: str = ""

    # --- App ---
    cors_origins: str = "http://localhost:5173"
    content_dir: str = Field(
        default="../content",
        validation_alias=AliasChoices("CONTENT_DIR", "content_dir"),
    )

    @property
    def fallback_models(self) -> list[str]:
        return [m.strip() for m in self.gemini_fallback_models.split(",") if m.strip()]

    @property
    def model_chain(self) -> list[str]:
        """Primary model followed by fallbacks, de-duplicated, order preserved."""
        seen: set[str] = set()
        chain: list[str] = []
        for model in [self.gemini_model, *self.fallback_models]:
            if model and model not in seen:
                seen.add(model)
                chain.append(model)
        return chain

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
