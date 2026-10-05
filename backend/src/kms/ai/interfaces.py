"""What the worker and search need from the AI vendors, independent of which vendor answers.

The fake adapters and the real ones implement the same classes, so their callers never know
which ones they are talking to.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from kms.ai.errors import RetryPolicy
from kms.ai.schema import Metadata


@dataclass(frozen=True)
class Description:
    """The metadata for one file and the model that wrote it.

    The model comes back with every answer because a real vision call may fall back to another
    model when the first one is overloaded.

    Attributes:
        metadata: The answer, validated but not normalised.
        model: The id of the model that answered.
    """

    metadata: Metadata
    model: str


@dataclass(frozen=True)
class PhotoDetails:
    """When and where a photo was taken, read from its own metadata.

    Given to the vision model next to the image, so it can name the place and the time.

    Attributes:
        taken_at: Local date and time as "YYYY-MM-DD HH:MM", or None if the photo has none.
        latitude: Decimal degrees, south negative, or None if the photo has no position.
        longitude: Decimal degrees, west negative, or None if the photo has no position.
    """

    taken_at: str | None
    latitude: float | None
    longitude: float | None


class Vision(ABC):
    """Describes one file as search metadata."""

    @abstractmethod
    def describe(
        self,
        content: bytes | str,
        asset_type: str,
        filename: str,
        photo_details: PhotoDetails | None,
        policy: RetryPolicy,
    ) -> Description:
        """Describe one file.

        Args:
            content: The prepared JPEG bytes for an image, the summary text for a text file.
            asset_type: "image" or "text".
            filename: The file's name as uploaded. Real models are not shown it; they judge the
                content, not the name.
            photo_details: When and where the photo was taken; None for a text file and for an
                image that carries neither.
            policy: How hard to try the vendor call, chosen by the caller.

        Returns:
            The metadata, validated but not normalised, and the model that wrote it.

        Raises:
            pydantic.ValidationError: The answer does not match the schema.
            Exception: A vendor error, raised as it comes.
        """


class Embedder(ABC):
    """Turns text and images into vectors in one shared space.

    Attributes:
        model: The embedding model's id. One embedder is always one model, because vectors
            from two models cannot be compared.
    """

    model: str

    @abstractmethod
    def embed(
        self,
        inputs: list[str | bytes],
        input_type: Literal["document", "query"],
        policy: RetryPolicy,
    ) -> list[list[float]]:
        """Embed a batch of inputs in one call.

        Args:
            inputs: Each item is embedded as text if it is a str, as an image if it is bytes.
            input_type: "document" for stored content, "query" for a search query.
            policy: How hard to try the vendor call, chosen by the caller.

        Returns:
            One vector per input, in the same order.

        Raises:
            Exception: A vendor error, raised as it comes.
        """


# The rerankers a search can ask for.
RerankerName = Literal["voyage", "jev"]
RERANKER_NAMES: tuple[RerankerName, ...] = ("voyage", "jev")


@dataclass(frozen=True)
class RerankDocument:
    """One search result as a reranker reads it: the part of the asset that matched, and the few
    facts that say what the asset is.

    Frozen and made of plain values, so a document can key the relevance cache.

    Attributes:
        text: The snippet's text: the passage, the description, the text read from the image, or
            the file name.
        kind: Which part of the asset `text` is: "metadata", "content", "image", "visible_text"
            or "filename".
        title: The asset's title; None before the asset is described.
        filename: The file's name as uploaded.
        tags: The asset's tags; empty before the asset is described.
    """

    text: str
    kind: str
    title: str | None
    filename: str
    tags: tuple[str, ...]


class Reranker(ABC):
    """Judges how well each of a list of search results answers the query, by reading the query
    and each result together.

    Attributes:
        model: The rerank model's id; a relevance is only ever reused for the same model.
    """

    model: str

    @abstractmethod
    def rerank(
        self, query: str, documents: list[RerankDocument], policy: RetryPolicy
    ) -> list[float] | None:
        """Score each document by how well it answers the query.

        Args:
            query: The query as typed.
            documents: One per result. Each reranker reads what it can use: a text-only model
                reads `text`, a model that takes structured input may read every field.
            policy: How hard to try the vendor call, chosen by the caller.

        Returns:
            One relevance from 0 to 1 per document, in the order of `documents`; None when this
            reranker gives no relevance.

        Raises:
            Exception: A vendor error, raised as it comes.
        """
