"""Every environment variable in one place.

Values are read from the environment and from a `.env` file in the working directory
(backend/.env locally, never committed). Names match the design doc; defaults are the
design's defaults.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- database ------------------------------------------------------------
    database_url: str = "postgresql+psycopg://kms:kms@localhost:5432/kms"
    # Used by the test suite instead of database_url, so tests never truncate dev data.
    test_database_url: str = "postgresql+psycopg://kms:kms@localhost:5432/kms_test"

    # --- AI vendors ----------------------------------------------------------
    ai_provider: Literal["fake", "real"] = "fake"
    gemini_api_key: str | None = None
    voyage_api_key: str | None = None
    # First of the D23 fallback list; the list itself replaces this setting in Phase 1 part 5.
    vision_model: str = "gemini-3-flash-preview"
    embedding_model: str = "voyage-multimodal-3.5"
    embedding_dims: int = 1024
    rerank_enabled: bool = False
    rerank_model: str = "rerank-2.5"

    # --- ingest --------------------------------------------------------------
    worker_enabled: bool = True
    worker_threads: int = 4
    lease_minutes: int = 10
    max_attempts: int = 3
    max_upload_bytes: int = 10 * 1024 * 1024
    chunk_target_tokens: int = 400
    chunk_max_tokens: int = 512
    chunk_overlap_tokens: int = 60
    summary_token_budget: int = 200_000

    # --- search --------------------------------------------------------------
    units_per_path: int = 100
    hnsw_ef_search: int = 100
    page_size: int = 20
    max_assets_per_query: int = 100
    query_cache_size: int = 4096

    # --- storage and seed ----------------------------------------------------
    blob_dir: Path = Path("./data/blobs")
    seed_dir: Path = Path("../seed")
    seed_on_start: bool = False

    # --- serving -------------------------------------------------------------
    static_dir: Path = Path(__file__).parent / "static"

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _psycopg_driver(cls, v: str) -> str:
        """Platforms hand out plain `postgresql://` URLs; SQLAlchemy needs the driver named."""
        if v.startswith("postgresql://"):
            return "postgresql+psycopg://" + v[len("postgresql://") :]
        if v.startswith("postgres://"):
            return "postgresql+psycopg://" + v[len("postgres://") :]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
