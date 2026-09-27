"""What the worker needs from the AI vendors, independent of which vendor answers.

The fake adapters and the real ones implement the same two classes, so the worker never knows
which ones it is talking to.
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
    """

    metadata: Metadata
    model: str


class Vision(ABC):
    @abstractmethod
    def describe(self, content: bytes | str, asset_type: str, filename: str) -> Description:
        """Describe one file: prepared JPEG bytes for an image, the summary text for a text file.

        The metadata is validated but not normalised. An answer that does not match the schema
        raises pydantic's ValidationError; a vendor error is raised as it comes.
        """


class Embedder(ABC):
    # One embedder is always one model: vectors from two models cannot be compared.
    model: str

    @abstractmethod
    def embed(
        self, inputs: list[str | bytes], input_type: Literal["document", "query"]
    ) -> list[list[float]]:
        """One vector per input, in order: a str is embedded as text, bytes as an image."""
