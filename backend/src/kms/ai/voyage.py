"""The real embedder: Voyage turns text and images into vectors in one shared space.

Inputs go to Voyage in batches, each batch retried on its own, and the vectors come back in the
order the inputs were given. The answer is checked before it is returned, so a wrong count or
length fails here rather than at the database insert.
"""

import functools
import io
import logging
import time
from typing import Literal

import voyageai
from PIL import Image

from kms.ai.errors import call_with_retries
from kms.ai.interfaces import Embedder

logger = logging.getLogger(__name__)

# Voyage allows 1,000 inputs and 320K tokens per call; 100 of our largest units, about 2,800
# tokens each, stay under the token limit.
MAX_INPUTS_PER_CALL = 100
# The SDK has no timeout by default, and a hung call would hold a worker.
VOYAGE_REQUEST_TIMEOUT_SECONDS = 60


class VoyageEmbedder(Embedder):
    """Embeds text and images with one Voyage multimodal model.

    Attributes:
        client: The Voyage client, built without the SDK's own retries.
        model: The embedding model's id.
        dims: The length of every vector, asked of Voyage on every call.
    """

    def __init__(self, client: voyageai.Client, model: str, dims: int):
        """Create the embedder.

        Args:
            client: The Voyage client to call through.
            model: The embedding model's id.
            dims: The length of every vector.
        """
        self.client = client
        self.model = model
        self.dims = dims

    def embed(
        self, inputs: list[str | bytes], input_type: Literal["document", "query"]
    ) -> list[list[float]]:
        """Embed the inputs, in batches of at most MAX_INPUTS_PER_CALL.

        If one batch still fails after its retries, the whole call fails and no vectors are
        kept; the caller embeds everything again on its next attempt.

        Args:
            inputs: A str is embedded as text; bytes are opened with Pillow as an image.
            input_type: "document" for stored content, "query" for a search query.

        Returns:
            One vector of length `dims` per input, in the same order; [] for no inputs, without
            a call.

        Raises:
            Exception: A vendor error, unchanged, when it is permanent or the retries ran out.
            ValueError: Voyage returned a different number of vectors than inputs, or a vector
                whose length is not `dims`.
        """
        if not inputs:
            return []

        # Voyage takes each input as a list of pieces; ours are one text or one image each.
        voyage_inputs = []
        for item in inputs:
            if isinstance(item, bytes):
                voyage_inputs.append([Image.open(io.BytesIO(item))])
            else:
                voyage_inputs.append([item])

        started = time.perf_counter()
        vectors = []
        calls = 0
        for start in range(0, len(voyage_inputs), MAX_INPUTS_PER_CALL):
            batch = voyage_inputs[start : start + MAX_INPUTS_PER_CALL]
            # partial binds this batch now; a lambda would read the loop variable when called.
            embed_batch = functools.partial(
                self.client.multimodal_embed,
                inputs=batch,
                model=self.model,
                input_type=input_type,
                truncation=True,
                output_dimension=self.dims,
            )
            result = call_with_retries(embed_batch, "voyage_embed")
            vectors.extend(result.embeddings)
            calls += 1
        duration_ms = (time.perf_counter() - started) * 1000

        if len(vectors) != len(inputs):
            raise ValueError(f"Voyage returned {len(vectors)} vectors for {len(inputs)} inputs")
        for vector in vectors:
            if len(vector) != self.dims:
                raise ValueError(
                    f"Voyage returned a vector of length {len(vector)}, expected {self.dims}"
                )

        logger.info(
            "voyage_embedded inputs=%d calls=%d duration_ms=%d",
            len(inputs),
            calls,
            duration_ms,
        )
        return vectors
