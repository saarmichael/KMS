"""Every environment variable in one place.

Values are read from the environment and from a `.env` file in the working directory
(backend/.env locally, never committed).
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationInfo, field_validator
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
    vision_provider: Literal["fake", "gemini"] = "fake"
    embedding_provider: Literal["fake", "voyage"] = "fake"
    # Retired settings, kept as fields only so that a leftover value in the environment or .env
    # stops the app at startup instead of being silently ignored.
    ai_provider: str | None = None
    rerank_enabled: str | None = None
    gemini_api_key: str | None = None
    voyage_api_key: str | None = None
    # The model settings below must name models of the chosen provider.
    # The vision models that describe images and text files, in the order they are tried: the
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
    # How many of one embed's batches are sent to the embedding vendor at once. A vendor may allow
    # many requests a minute, while a large file's batches together pass its tokens-per-minute
    # limit.
    embed_parallel_calls: int = Field(default=20, ge=1)
    rerank_provider: Literal["none", "voyage"] = "none"
    rerank_model: str = "rerank-2.5"
    # Where the real vendors' answers are recorded and replayed from; empty turns recording
    # off. A string rather than a Path, so that empty can mean off. Off unless set, because
    # every new search query adds a file, so a deployment would record without end.
    ai_cache_dir: str = ""

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
    # How many of the top results the reranker scores; one page, so only page 1 costs a call.
    rerank_candidates: int = Field(default=20, ge=1)
    # How many (query, text) relevances are remembered, so a change of order or filter does not
    # pay for the same scores again.
    rerank_cache_size: int = Field(default=2000, ge=1)
    query_cache_size: int = 4096

    # --- storage and seed ----------------------------------------------------
    blob_store: Literal["local"] = "local"
    # The folder the local blob store keeps the files in.
    blob_dir: Path = Path("./data/blobs")
    seed_dir: Path = Path("../seed")
    seed_on_start: bool = False

    # --- serving -------------------------------------------------------------
    # The one password for the whole app (any username); empty leaves the app open.
    app_password: str = ""
    # A shared demo deployment: the UI greys out deleting a collection and the API refuses it.
    demo_mode: bool = False
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

    @field_validator("ai_provider", "rerank_enabled")
    @classmethod
    def _refuse_retired_setting(cls, value: str | None, info: ValidationInfo) -> None:
        """Refuse a retired setting that is still set, naming what replaced it.

        A deployment that kept an old setting would otherwise run on the defaults unnoticed.

        Args:
            value: The retired setting's value as configured; None when it is not set.
            info: Pydantic's validation context, which names the field being checked.

        Returns:
            None, as the retired setting is never read.

        Raises:
            ValueError: The retired setting is set.
        """
        if value is None:
            return None
        if info.field_name == "ai_provider":
            raise ValueError(
                "AI_PROVIDER was replaced by VISION_PROVIDER, EMBEDDING_PROVIDER"
                " and RERANK_PROVIDER"
            )
        raise ValueError("RERANK_ENABLED was replaced by RERANK_PROVIDER")


@lru_cache
def get_settings() -> Settings:
    """The settings, read once and cached for the life of the process."""
    return Settings()
