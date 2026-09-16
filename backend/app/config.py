"""Centralized application settings.

All configuration is read from environment variables (see `.env.example` at
the repo root). We use `pydantic-settings` so misconfiguration fails fast and
loudly at process startup instead of deep inside a graph node.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM provider ---------------------------------------------------
    llm_provider: str = "openai"  # "openai" | "anthropic"
    llm_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-3-5-haiku-latest"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    embedding_model: str = "text-embedding-3-small"
    # Structuring/summarizing an existing clinical note should be as
    # deterministic as possible -- this is documentation, not creative
    # writing, and the whole point is to avoid the model inventing content.
    llm_temperature: float = 0.0

    # --- Postgres (prompts, patients/encounters history, LangGraph checkpoints) --
    # SQLAlchemy (sync engine) uses the psycopg3 dialect: postgresql+psycopg://
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/clinical_docs"
    )
    # AsyncPostgresSaver needs a plain psycopg-style DSN (no "+psycopg" driver
    # suffix); we strip it in db/checkpointer.py.

    # --- Notes -------------------------------------------------------------
    # Where uploaded notes are stored (git-ignored). Relative paths are
    # resolved from the backend/ working directory.
    upload_dir: str = "./data/uploads"
    # Where the bundled synthetic sample clinical notes live, so the "run a
    # sample note" zero-setup demo path and the seed scripts can find them.
    # Defaults to the repo-root `sample-data/` folder one level up from
    # `backend/`; overridden to `/app/sample-data` in Docker (see
    # docker-compose.yml, which mounts it read-only).
    sample_data_dir: str = "../sample-data"

    # --- Milvus Lite (embedded vector store, no server/docker needed) ---
    # Used for semantic ICD-10 code lookup only -- see
    # app/tools/icd10_lookup.py. Suggestions from this collection are always
    # "for clinician confirmation", never auto-applied to a patient's record.
    milvus_lite_path: str = "./data/milvus_icd10.db"
    milvus_collection: str = "icd10_codes"
    icd10_top_k: int = 3

    # --- API ---------------------------------------------------------------
    cors_allow_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
