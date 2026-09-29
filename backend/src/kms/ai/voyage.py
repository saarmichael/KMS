"""The real embedder: Voyage turns text and images into vectors in one shared space. And the real
reranker: Voyage reads a query and each search result together and scores how well they match.

Inputs go to Voyage in batches sent at the same time, each batch retried on its own, and the
vectors come back in the order the inputs were given. The answer is checked before it is
returned, so a wrong count or length fails here rather than at the database insert.
"""

import functools
import io
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from typing import Literal

import voyageai
from PIL import Image
from voyageai import error as voyage_errors

from kms.ai.errors import ErrorVerdict, RetryPolicy, call_with_retries
from kms.ai.interfaces import Embedder, Reranker

logger = logging.getLogger(__name__)

# Voyage allows 1,000 inputs and 320K tokens per call; 100 of our largest units, about 2,800
# tokens each, stay under the token limit.
MAX_INPUTS_PER_CALL = 100


def classify_voyage_error(error: Exception) -> ErrorVerdict:
    """Say whether a failed Voyage call is worth trying again.

    Args:
        error: Whatever the Voyage call raised.

    Returns:
        Retryable for a rate limit, a server error, an unavailable service, a timeout, a dropped
        connection, Voyage's "try again", and any other 429 or 5xx; not retryable for anything
        else, a bad key or a bad request included. Voyage never says how long to wait, so there
        is no server wait. Never raises.
    """
    if not isinstance(error, voyage_errors.VoyageError):
        return ErrorVerdict(retryable=False, server_wait_seconds=None)
    retryable_errors = (
        voyage_errors.RateLimitError,
        voyage_errors.ServerError,
        voyage_errors.ServiceUnavailableError,
        voyage_errors.Timeout,
        voyage_errors.APIConnectionError,
        voyage_errors.TryAgain,
    )
    if isinstance(error, retryable_errors):
        return ErrorVerdict(retryable=True, server_wait_seconds=None)
    status = error.http_status
    if status is not None and (
        status == HTTPStatus.TOO_MANY_REQUESTS or status >= HTTPStatus.INTERNAL_SERVER_ERROR
    ):
        return ErrorVerdict(retryable=True, server_wait_seconds=None)
    return ErrorVerdict(retryable=False, server_wait_seconds=None)


class VoyageClients:
    """The Voyage clients of one API key, one per timeout.

    Voyage's SDK sets the timeout on the client, not on a call, so each policy's timeout gets a
    client of its own. The clients are built without the SDK's own retries, so only our policy
    decides when to try again.

    Attributes:
        api_key: The Voyage API key every client uses.
    """

    def __init__(self, api_key: str):
        """Create the set, with no client built yet.

        Args:
            api_key: The Voyage API key.
        """
        self.api_key = api_key
        self._clients: dict[float, voyageai.Client] = {}
        # Worker threads and searches ask for clients at the same time.
        self._lock = threading.Lock()

    def for_timeout(self, seconds: float) -> voyageai.Client:
        """Return the client whose requests time out after `seconds`, building it on first use.

        Args:
            seconds: The timeout of every request made through the client.

        Returns:
            The same client for the same timeout on every call. Never raises.
        """
        with self._lock:
            client = self._clients.get(seconds)
            if client is None:
                client = voyageai.Client(api_key=self.api_key, max_retries=0, timeout=seconds)
                self._clients[seconds] = client
            return client


class VoyageEmbedder(Embedder):
    """Embeds text and images with one Voyage multimodal model.

    Attributes:
        clients: The Voyage clients, one per timeout.
        model: The embedding model's id.
        dims: The length of every vector, asked of Voyage on every call.
        parallel_calls: The most batches of one `embed` call sent to Voyage at once.
    """

    def __init__(self, clients: VoyageClients, model: str, dims: int, parallel_calls: int):
        """Create the embedder.

        Args:
            clients: The Voyage clients to call through.
            model: The embedding model's id.
            dims: The length of every vector.
            parallel_calls: The most batches of one `embed` call sent to Voyage at once.
        """
        self.clients = clients
        self.model = model
        self.dims = dims
        self.parallel_calls = parallel_calls

    def embed(
        self,
        inputs: list[str | bytes],
        input_type: Literal["document", "query"],
        policy: RetryPolicy,
    ) -> list[list[float]]:
        """Embed the inputs, in batches of at most MAX_INPUTS_PER_CALL sent at the same time.

        Up to `parallel_calls` batches are in flight at once. If one batch still fails after its
        retries, the whole call fails and no vectors are kept; the caller embeds everything again
        on its next attempt.

        Args:
            inputs: A str is embedded as text; bytes are opened with Pillow as an image.
            input_type: "document" for stored content, "query" for a search query.
            policy: How hard to try each batch, and how long each request may take.

        Returns:
            One vector of length `dims` per input, in the same order; [] for no inputs, without
            a call.

        Raises:
            Exception: A vendor error, unchanged, when it is not retryable or the retries ran out;
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
        client = self.clients.for_timeout(policy.timeout_seconds)

        started = time.perf_counter()
        vectors = []
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = []
            for batch in batches:
                # partial binds this batch now; a lambda would read the loop variable when called.
                embed_batch = functools.partial(
                    client.multimodal_embed,
                    inputs=batch,
                    model=self.model,
                    input_type=input_type,
                    truncation=True,
                    output_dimension=self.dims,
                )
                futures.append(
                    executor.submit(
                        call_with_retries,
                        embed_batch,
                        "voyage_embed",
                        classify_voyage_error,
                        policy,
                    )
                )
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
        clients: The Voyage clients, one per timeout.
        model: The rerank model's id.
    """

    def __init__(self, clients: VoyageClients, model: str):
        """Create the reranker.

        Args:
            clients: The Voyage clients to call through.
            model: The rerank model's id.
        """
        self.clients = clients
        self.model = model

    def rerank(self, query: str, documents: list[str], policy: RetryPolicy) -> list[float]:
        """Score each document against the query in one Voyage call.

        Args:
            query: The query as typed.
            documents: One text per result. A text too long for the model is cut short by
                Voyage rather than refused.
            policy: How hard to try, and how long the request may take.

        Returns:
            One relevance from 0 to 1 per document, in the order of `documents`; [] for no
            documents, without a call.

        Raises:
            Exception: A vendor error, unchanged, when it is not retryable or the retries ran out.
            ValueError: Voyage returned a different number of scores than documents.
        """
        if not documents:
            return []

        client = self.clients.for_timeout(policy.timeout_seconds)
        rerank_call = functools.partial(
            client.rerank,
            query=query,
            documents=documents,
            model=self.model,
            truncation=True,
        )
        started = time.perf_counter()
        answer = call_with_retries(rerank_call, "voyage_rerank", classify_voyage_error, policy)
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
