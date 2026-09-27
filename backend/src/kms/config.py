"""Every environment variable in one place.

Values are read from the environment and from a `.env` file in the working directory
(backend/.env locally, never committed).
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """The app's configuration.

    Each field is read from the environment variable of the same name, falling back to the
    default given here.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- database ------------------------------------------------------------
    database_url: str = "postgresql+psycopg://kms:kms@localhost:5432/kms"
    # Used by the test suite instead of database_url, so tests never truncate dev data.
    test_database_url: str = "postgresql+psycopg://kms:kms@localhost:5432/kms_test"

    # --- AI vendors ----------------------------------------------------------
    ai_provider: Literal["fake", "real"] = "fake"
    gemini_api_key: str | None = None
    voyage_api_key: str | None = None
    # The Gemini models that describe images and text files, in the order they are tried: the
    # next one answers when the one before is overloaded. A JSON list in the environment.
    vision_models: list[str] = Field(
        default=[
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite-preview",
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite",
        ],
        min_length=1,
    )
    embedding_model: str = "voyage-multimodal-3.5"
    embedding_dims: int = 1024
    rerank_enabled: bool = False
    rerank_model: str = "rerank-2.5"
    # Where the real vendors' answers are recorded and replayed from; empty turns recording
    # off. A string rather than a Path, so that empty can mean off.
    ai_cache_dir: str = "./recordings"

    # --- ingest --------------------------------------------------------------
    worker_enabled: bool = True
    worker_threads: int = 4
    lease_minutes: int = 10
    max_attempts: int = 3
    max_upload_bytes: int = 10 * 1024 * 1024
    # About 400 tokens with 15% overlap; characters, so they match the stored offsets.
    chunk_size_chars: int = 1600
    chunk_overlap_chars: int = 240
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
    # The one password for the whole app (any username); empty leaves the app open.
    app_password: str = ""
    static_dir: Path = Path(__file__).parent / "static"

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _psycopg_driver(cls, v: str) -> str:
        """Name the psycopg driver in a database URL that lacks it.

        Platforms hand out plain `postgresql://` URLs; SQLAlchemy needs the driver named.

        Args:
            v: The database URL as configured.

        Returns:
            The URL with a `postgresql+psycopg://` scheme; a URL with any other scheme unchanged.
        """
        if v.startswith("postgresql://"):
            return "postgresql+psycopg://" + v[len("postgresql://") :]
        if v.startswith("postgres://"):
            return "postgresql+psycopg://" + v[len("postgres://") :]
        return v


@lru_cache
def get_settings() -> Settings:
    """The settings, read once and cached for the life of the process."""
    return Settings()
