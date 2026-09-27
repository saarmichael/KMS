"""Deterministic stand-ins for the AI vendors: no network, no keys, no cost.

They make the whole pipeline runnable locally and in tests. They prove that our code moves the
right data around, not that search understands meaning; that is the real models' job.
"""

import hashlib
import logging
import math
import random
import re
from typing import Literal

from kms.ai.fake_fixtures import FIXTURES
from kms.ai.interfaces import Description, Embedder, PhotoDetails, Vision
from kms.ai.schema import Metadata

logger = logging.getLogger(__name__)

# A file whose name contains this word always gets an answer that fails validation, so the
# retry and failure paths can be shown without a real model misbehaving.
INVALID_MARKER = "invalid"
# Cut off mid-object: what a model that stopped early would send.
BROKEN_ANSWER = '{"title": "Half an answer", "description": '


class FakeVision(Vision):
    """Answers from hand-written fixtures by filename, so no model is called.

    Attributes:
        model: "fake-vision", reported as the model that answered.
    """

    model = "fake-vision"

    def describe(
        self,
        content: bytes | str,
        asset_type: str,
        filename: str,
        photo_details: PhotoDetails | None,
    ) -> Description:
        """Return the fixture for this filename, or generic metadata for an unknown one.

        Args:
            content: Ignored.
            asset_type: "image" or "text"; shapes the generic answer.
            filename: The fixture key.
            photo_details: Ignored.

        Returns:
            The fixture or the generic metadata, with model "fake-vision".

        Raises:
            pydantic.ValidationError: The filename contains "invalid".
        """
        if INVALID_MARKER in filename:
            logger.info("fake_vision_invalid filename=%r", filename)
            # Parsing a broken answer raises the same error a bad real answer would.
            Metadata.model_validate_json(BROKEN_ANSWER)

        metadata = FIXTURES.get(filename)
        if metadata is None:
            logger.info("fake_vision_generic filename=%r", filename)
            if asset_type == "image":
                description, image_type = "An uploaded image.", "other"
            else:
                description, image_type = "An uploaded text file.", None
            metadata = Metadata(
                title=filename,
                description=description,
                tags=[],
                visible_text="",
                image_type=image_type,
            )
        return Description(metadata=metadata, model=self.model)


class FakeEmbedder(Embedder):
    """Deterministic vectors without a model.

    Text becomes a hashed bag of words, so texts that share words point the same way. Images
    get a vector drawn from the hash of their bytes, the same bytes always giving the same one.

    Attributes:
        model: "fake-embedder", stored with every vector like a real model id.
        dims: The length of every vector.
    """

    model = "fake-embedder"

    def __init__(self, dims: int):
        """Create an embedder.

        Args:
            dims: The length of every vector it returns.
        """
        self.dims = dims

    def embed(
        self, inputs: list[str | bytes], input_type: Literal["document", "query"]
    ) -> list[list[float]]:
        """Embed each input; never raises.

        Args:
            inputs: A str is split into words; bytes, and a str with no words, are hashed whole.
            input_type: Ignored.

        Returns:
            One vector of length 1 per input, in the same order.
        """
        vectors = []
        for item in inputs:
            if isinstance(item, bytes):
                words = []
                hashed_bytes = item
            else:
                words = re.findall(r"\w+", item.lower())
                # Text with no words would give an all-zero vector, which has no direction and
                # cannot be compared by cosine, so it is treated like bytes instead.
                hashed_bytes = None if words else item.encode()

            if hashed_bytes is not None:
                seeded = random.Random(hashlib.sha256(hashed_bytes).hexdigest())
                vector = [seeded.gauss(0.0, 1.0) for _ in range(self.dims)]
            else:
                vector = [0.0] * self.dims
                for word in words:
                    # sha256, not hash(): Python salts hash() per process, so positions would
                    # move after a restart and stored vectors would stop matching new ones.
                    position = int(hashlib.sha256(word.encode()).hexdigest(), 16) % self.dims
                    vector[position] += 1.0

            length = math.sqrt(sum(value * value for value in vector))
            vectors.append([value / length for value in vector])
        return vectors
