"""What the worker and search need from the AI vendors, independent of which vendor answers.

The fake adapters and the real ones implement the same classes, so their callers never know
which ones they are talking to.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

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
    ) -> Description:
        """Describe one file.

        Args:
            content: The prepared JPEG bytes for an image, the summary text for a text file.
            asset_type: "image" or "text".
            filename: The file's name as uploaded. Real models are not shown it; they judge the
                content, not the name.
            photo_details: When and where the photo was taken; None for a text file and for an
                image that carries neither.

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
        self, inputs: list[str | bytes], input_type: Literal["document", "query"]
    ) -> list[list[float]]:
        """Embed a batch of inputs in one call.

        Args:
            inputs: Each item is embedded as text if it is a str, as an image if it is bytes.
            input_type: "document" for stored content, "query" for a search query.

        Returns:
            One vector per input, in the same order.

        Raises:
            Exception: A vendor error, raised as it comes.
        """


class Reranker(ABC):
    """Judges how well each of a short list of search results answers the query, by reading the
    query and each result together."""

    @abstractmethod
    def rerank(self, query: str, documents: list[str]) -> list[float] | None:
        """Score each document by how well it answers the query.

        Args:
            query: The query as typed.
            documents: One text per result.

        Returns:
            One relevance from 0 to 1 per document, in the order of `documents`; None when this
            reranker gives no relevance.

        Raises:
            Exception: A vendor error, raised as it comes.
        """
