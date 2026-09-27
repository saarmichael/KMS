"""Response bodies of the asset, collection and search endpoints, written by hand from the API
contract.

The class names are the contract's type names, so the backend and the frontend use one name
for each shape.
"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.engine import RowMapping

from kms.search import MatchKind

# Lowercase letters, digits, "-" and "_", 1 to 64 characters: safe in a URL path as it is.
COLLECTION_NAME_PATTERN = r"^[a-z0-9_-]{1,64}$"


class AssetMetadata(BaseModel):
    """What the describer found in an asset; present only once the asset is ready."""

    title: str
    description: str
    tags: list[str]
    visible_text: str | None
    image_type: Literal["photo", "screenshot", "document", "diagram", "other"] | None
    vision_model: str | None


class Asset(BaseModel):
    """One uploaded file and where it stands in processing."""

    id: UUID
    collection: str
    filename: str
    aliases: list[str]
    asset_type: Literal["image", "text"]
    mime: str
    size_bytes: int
    status: Literal["pending", "processing", "ready", "failed"]
    error: str | None
    created_at: datetime
    metadata: AssetMetadata | None

    @classmethod
    def from_row(cls, row: RowMapping) -> "Asset":
        """Build the API shape from an `assets` row; metadata exists only once it is ready.

        Args:
            row: One row of the `assets` table.

        Returns:
            The asset as the API sends it.
        """
        metadata = None
        if row["status"] == "ready":
            metadata = AssetMetadata(
                title=row["title"],
                description=row["description"],
                tags=row["tags"],
                visible_text=row["visible_text"],
                image_type=row["image_type"],
                vision_model=row["vision_model"],
            )
        return cls(
            id=row["id"],
            collection=row["collection"],
            filename=row["filename"],
            aliases=row["aliases"],
            asset_type=row["asset_type"],
            mime=row["mime"],
            size_bytes=row["size_bytes"],
            status=row["status"],
            error=row["error"],
            # Postgres returns the time in the session's time zone; the API always speaks UTC.
            created_at=row["created_at"].astimezone(UTC),
            metadata=metadata,
        )


class UploadResponse(BaseModel):
    """The answer to an upload: the asset, and whether its bytes were already stored."""

    deduplicated: bool
    asset: Asset


class AssetList(BaseModel):
    """The assets of one collection, newest first."""

    assets: list[Asset]


class Collection(BaseModel):
    """A collection and how many assets it holds."""

    name: str
    asset_count: int


class CollectionList(BaseModel):
    """Every collection that holds at least one asset, sorted by name."""

    collections: list[Collection]


class Snippet(BaseModel):
    """Why a search result matched: the part of the asset that matched best."""

    kind: Literal["metadata", "content", "image", "filename"]
    text: str
    start_char: int | None
    end_char: int | None


class SearchResult(BaseModel):
    """One asset found by a search, with its score and why it matched."""

    asset: Asset
    score: float
    snippet: Snippet
    match: MatchKind


class SearchResponse(BaseModel):
    """One page of search results, best first."""

    results: list[SearchResult]
    page: int
    page_size: int
    has_more: bool
