"""
app/core/config.py
Central configuration — loaded once at startup via pydantic-settings.
All values come from environment variables / .env file.
"""
from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ────────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_name: str = "Elevate AI"
    app_version: str = "0.1.0"
    debug: bool = False

    # ── Database — defaults to local PostgreSQL ────────────────────────────
    # database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/skilldb"
    database_url: str = "sqlite+aiosqlite:///./skilldb.sqlite3"
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # ── Auth ───────────────────────────────────────────────────────────────
    secret_key: str = "change-me-in-production-must-be-at-least-32-characters"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # ── LLM ───────────────────────────────────────────────────────────────
    # ── Gemini ─────────────────────────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    llm_log_payloads: bool = False
    llm_timeout_seconds: int = 30

    # ── Redis (optional until Week 3) ─────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── LangSmith / LangChain tracing (optional) ──────────────────────────
    # Accept LANGSMITH_* or legacy LANGCHAIN_* in .env
    langchain_tracing_v2: bool = Field(
        default=False,
        validation_alias=AliasChoices("LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING"),
    )
    langchain_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LANGCHAIN_API_KEY", "LANGSMITH_API_KEY"),
    )
    langchain_project: str = Field(
        default="skill-intelligence",
        validation_alias=AliasChoices("LANGCHAIN_PROJECT", "LANGSMITH_PROJECT"),
    )

    # ── File upload ───────────────────────────────────────────────────────
    max_upload_size_mb: int = 10
    upload_dir: str = "/tmp/skill-intelligence/uploads"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()