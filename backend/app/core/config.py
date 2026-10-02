"""
app/core/config.py
──────────────────
Centralised settings loaded from environment variables / .env file.
All other modules should import `get_settings()` rather than accessing
os.environ directly so that the config is validated once at startup.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import AnyUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────────────────────
    groq_api_key: str = Field(..., description="Groq API key")
    model_names: List[str] = Field(
        default=["llama-3.3-70b-versatile"],
        description="Comma-separated list of allowed Groq model identifiers",
    )
    default_model_name: str = Field(
        default="llama-3.3-70b-versatile",
        description="Model used when the caller does not specify one",
    )

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL (redis[s]://[user:pass@]host:port/db)",
    )
    cache_ttl_seconds: int = Field(default=3600)

    # ── ChromaDB ─────────────────────────────────────────────────────────────
    chroma_persist_dir: str = Field(default="./data/chroma")
    chroma_collection_name: str = Field(default="rag_documents")

    # ── Embeddings ────────────────────────────────────────────────────────────
    embedding_model_name: str = Field(default="all-MiniLM-L6-v2")

    # ── Retrieval ─────────────────────────────────────────────────────────────
    retriever_top_k: int = Field(default=20, ge=1, le=200)
    reranker_top_n: int = Field(default=5, ge=1, le=50)

    # ── Application ───────────────────────────────────────────────────────────
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    cors_origins: List[str] = Field(default=["http://localhost:3000"])

    # ── Validators ────────────────────────────────────────────────────────────
    @field_validator("model_names", "cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, v: str | list) -> list:
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @field_validator("default_model_name")
    @classmethod
    def _default_in_allowed(cls, v: str, info) -> str:
        allowed = info.data.get("model_names", [])
        if allowed and v not in allowed:
            raise ValueError(
                f"default_model_name '{v}' must be one of model_names: {allowed}"
            )
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()
