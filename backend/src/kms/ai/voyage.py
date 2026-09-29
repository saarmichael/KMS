"""The real embedder: Voyage turns text and images into vectors in one shared space. And the real
reranker: Voyage reads a query and each search result together and scores how well they match.

Inputs go to Voyage in batches sent at the same time, each batch retried on its own, and the
vectors come back in the order the inputs were given. The answer is checked before it is
returned, so a wrong count or length fails here rather than at the database insert.
"""

import functools
import io
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

import voyageai
from PIL import Image

from kms.ai.errors import call_with_retries
from kms.ai.interfaces import Embedder, Reranker

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
        parallel_calls: The most batches of one `embed` call sent to Voyage at once.
    """

    def __init__(self, client: voyageai.Client, model: str, dims: int, parallel_calls: int):
        """Create the embedder.

        Args:
            client: The Voyage client to call through.
            model: The embedding model's id.
            dims: The length of every vector.
            parallel_calls: The most batches of one `embed` call sent to Voyage at once.
        """
        self.client = client
        self.model = model
        self.dims = dims
        self.parallel_calls = parallel_calls

    def embed(
        self, inputs: list[str | bytes], input_type: Literal["document", "query"]
    ) -> list[list[float]]:
        """Embed the inputs, in batches of at most MAX_INPUTS_PER_CALL sent at the same time.

        Up to `parallel_calls` batches are in flight at once. If one batch still fails after its
        retries, the whole call fails and no vectors are kept; the caller embeds everything again
        on its next attempt.

        Args:
            inputs: A str is embedded as text; bytes are opened with Pillow as an image.
            input_type: "document" for stored content, "query" for a search query.

        Returns:
            One vector of length `dims` per input, in the same order; [] for no inputs, without
            a call.

        Raises:
            Exception: A vendor error, unchanged, when it is permanent or the retries ran out;
                with several failed batches, the error of the first one in input order.
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

        batches = []
        for start in range(0, len(voyage_inputs), MAX_INPUTS_PER_CALL):
            batches.append(voyage_inputs[start : start + MAX_INPUTS_PER_CALL])
        parallel = min(len(batches), self.parallel_calls)

        started = time.perf_counter()
        vectors = []
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = []
            for batch in batches:
                # partial binds this batch now; a lambda would read the loop variable when called.
                embed_batch = functools.partial(
                    self.client.multimodal_embed,
                    inputs=batch,
                    model=self.model,
                    input_type=input_type,
                    truncation=True,
                    output_dimension=self.dims,
                )
                futures.append(executor.submit(call_with_retries, embed_batch, "voyage_embed"))
            # Results are read in input order, so the vectors line up with the inputs whatever
            # order the calls finish in.
            try:
                for future in futures:
                    vectors.extend(future.result().embeddings)
            except Exception:
                # The whole call has failed: batches not sent yet are dropped, and leaving the
                # block waits for the calls already in flight.
                executor.shutdown(cancel_futures=True)
                raise
        duration_ms = (time.perf_counter() - started) * 1000

        if len(vectors) != len(inputs):
            raise ValueError(f"Voyage returned {len(vectors)} vectors for {len(inputs)} inputs")
        for vector in vectors:
            if len(vector) != self.dims:
                raise ValueError(
                    f"Voyage returned a vector of length {len(vector)}, expected {self.dims}"
                )

        logger.info(
            "voyage_embedded inputs=%d calls=%d parallel=%d duration_ms=%d",
            len(inputs),
            len(batches),
            parallel,
            duration_ms,
        )
        return vectors


class VoyageReranker(Reranker):
    """Scores search results against a query with one Voyage rerank model.

    Attributes:
        client: The Voyage client, built without the SDK's own retries.
        model: The rerank model's id.
    """

    def __init__(self, client: voyageai.Client, model: str):
        """Create the reranker.

        Args:
            client: The Voyage client to call through.
            model: The rerank model's id.
        """
        self.client = client
        self.model = model

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        """Score each document against the query in one Voyage call.

        Args:
            query: The query as typed.
            documents: One text per result. A text too long for the model is cut short by
                Voyage rather than refused.

        Returns:
            One relevance from 0 to 1 per document, in the order of `documents`; [] for no
            documents, without a call.

        Raises:
            Exception: A vendor error, unchanged, when it is permanent or the retries ran out.
            ValueError: Voyage returned a different number of scores than documents.
        """
        if not documents:
            return []

        rerank_call = functools.partial(
            self.client.rerank,
            query=query,
            documents=documents,
            model=self.model,
            truncation=True,
        )
        started = time.perf_counter()
        answer = call_with_retries(rerank_call, "voyage_rerank")
        duration_ms = (time.perf_counter() - started) * 1000

        if len(answer.results) != len(documents):
            raise ValueError(
                f"Voyage returned {len(answer.results)} scores for {len(documents)} documents"
            )
        # Voyage lists the results best first; each carries the position of its document.
        relevances = [0.0] * len(documents)
        for result in answer.results:
            relevances[result.index] = result.relevance_score

        logger.info("voyage_reranked documents=%d duration_ms=%d", len(documents), duration_ms)
        return relevances
