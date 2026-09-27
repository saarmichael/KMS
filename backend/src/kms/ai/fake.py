"""Deterministic stand-ins for the AI vendors: no network, no keys, no cost.

They make the whole pipeline runnable locally and in tests. They prove that our code moves the
right data around, not that search understands meaning; that is the real models' job.
"""

import hashlib
import math
import random
import re
from typing import Literal

from kms.ai.fake_fixtures import FIXTURES
from kms.ai.interfaces import Description, Embedder, Vision
from kms.ai.schema import Metadata

# A file whose name contains this word always gets an answer that fails validation, so the
# retry and failure paths can be shown without a real model misbehaving.
INVALID_MARKER = "invalid"
# Cut off mid-object: what a model that stopped early would send.
BROKEN_ANSWER = '{"title": "Half an answer", "description": '


class FakeVision(Vision):
    model = "fake-vision"

    def describe(self, content: bytes | str, asset_type: str, filename: str) -> Description:
        if INVALID_MARKER in filename:
            # Parsing a broken answer raises the same error a bad real answer would.
            Metadata.model_validate_json(BROKEN_ANSWER)

        metadata = FIXTURES.get(filename)
        if metadata is None:
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
    """Text: a hashed bag of words, so texts that share words point the same way.
    Images: a vector drawn from the hash of the bytes, the same bytes always giving the same one.
    """

    model = "fake-embedder"

    def __init__(self, dims: int):
        self.dims = dims

    def embed(
        self, inputs: list[str | bytes], input_type: Literal["document", "query"]
    ) -> list[list[float]]:
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
