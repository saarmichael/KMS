"""The Jev reranker: TypeSafe's Jev reads a query and one search result and answers, as a calibrated
probability, whether the result answers the query.

Jev generates no text. It is given a `state` (here the query and one result, as JSON) and typed
questions about it; a yes/no question (a "noul") comes back as the probability of yes. That
probability is the relevance.

Each result is asked about in a call of its own, and the calls are sent at the same time. One call
could hold many results, but a call is capped at about 32,000 tokens, which a hundred passages
pass, and a result judged next to others is scored against them: the same result gets a different
relevance in a different list, so it could not be remembered on its own.
"""

import functools
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from typesafe_sdk import (
    Noul,
    TypeSafeAPIConnectionError,
    TypeSafeClient,
    TypeSafeInternalServerError,
    TypeSafeRateLimitError,
)
from typesafe_sdk import RetryPolicy as TypeSafeRetryPolicy

from kms.ai.errors import ErrorVerdict, RetryPolicy, call_with_retries
from kms.ai.interfaces import RerankDocument, Reranker

logger = logging.getLogger(__name__)

# The answer's name in Jev's reply; any name would do, there is only one question.
QUESTION_NAME = "answers_query"
# Worded like the relevance the API promises: how well the result answers the query. Asking
# whether a result is "relevant" was tried too; it rated most results of a place name near 1 and
# told them apart less well.
QUESTION = Noul(instructions="Does this search result answer the search query?")

# How each kind of snippet is named to Jev, in the words a person would use.
MATCHED_PART_NAMES = {
    "metadata": "description",
    "content": "passage of the file",
    "image": "description of the image",
    "visible_text": "text read from the image",
    "filename": "file name",
}


def classify_jev_error(error: Exception) -> ErrorVerdict:
    """Say whether a failed Jev call is worth trying again.

    Args:
        error: Whatever the TypeSafe call raised.

    Returns:
        Retryable for a rate limit (with the wait Jev asked for, if it gave one), a server error,
        a timeout and a dropped connection; not retryable for anything else, a bad key and a
        request over Jev's token limit included. Never raises.
    """
    if isinstance(error, TypeSafeRateLimitError):
        wait_seconds = None
        if error.retry_after_ms is not None:
            wait_seconds = error.retry_after_ms / 1000
        return ErrorVerdict(retryable=True, server_wait_seconds=wait_seconds)
    # A timeout is a kind of connection error in the SDK.
    if isinstance(error, TypeSafeInternalServerError | TypeSafeAPIConnectionError):
        return ErrorVerdict(retryable=True, server_wait_seconds=None)
    return ErrorVerdict(retryable=False, server_wait_seconds=None)


def jev_state(query: str, document: RerankDocument) -> dict:
    """Build what Jev is asked about: the query and one result.

    Jev reads structured state, so the result goes with its title, file name and tags: they say
    what the asset is when the matched part alone does not, as with a file name or a passage
    from the middle of a book.

    Args:
        query: The query as typed.
        document: The result.

    Returns:
        A JSON-ready dict with the query and the result. A result not yet described has no title
        and no tags, and they are left out. Never raises.
    """
    result = {}
    if document.title is not None:
        result["title"] = document.title
    result["file_name"] = document.filename
    if document.tags:
        result["tags"] = list(document.tags)
    result["matched_part"] = MATCHED_PART_NAMES.get(document.kind, document.kind)
    result["matched_text"] = document.text
    return {"query": query, "result": result}


class JevReranker(Reranker):
    """Scores search results against a query with Jev, one call per result, sent together.

    Attributes:
        client: The TypeSafe client, built with the SDK's own retries off, so only our policy
            decides when to try again. One client for every timeout: the SDK takes the timeout
            per call.
        model: The Jev model's id.
        parallel_calls: The most calls of one `rerank` sent to Jev at once.
    """

    def __init__(self, client: TypeSafeClient, model: str, parallel_calls: int):
        """Create the reranker.

        Args:
            client: The TypeSafe client to call through.
            model: The Jev model's id.
            parallel_calls: The most calls of one `rerank` sent at once.
        """
        self.client = client
        self.model = model
        self.parallel_calls = parallel_calls

    def rerank(
        self, query: str, documents: list[RerankDocument], policy: RetryPolicy
    ) -> list[float]:
        """Score each document against the query, one Jev call each, up to `parallel_calls` at
        once.

        If one call still fails after its retries, the whole rerank fails and no relevance is
        kept, as with a failed Voyage call: a list with holes would order the results it scored
        above the ones it could not.

        Args:
            query: The query as typed.
            documents: One per result.
            policy: How hard to try each call, and how long each request may take.

        Returns:
            One relevance from 0 to 1 per document (Jev's probability that it answers the
            query), in the order of `documents`; [] for no documents, without a call.

        Raises:
            Exception: A vendor error, unchanged, when it is not retryable or the retries ran
                out; with several failed calls, the error of the first one in document order.
        """
        if not documents:
            return []

        parallel = min(len(documents), self.parallel_calls)
        started = time.perf_counter()
        relevances = []
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = []
            for document in documents:
                # partial binds this document now; a lambda would read the loop variable when
                # called.
                ask_jev = functools.partial(
                    self.client.system_one,
                    state=jev_state(query, document),
                    questions={QUESTION_NAME: QUESTION},
                    model=self.model,
                    timeout=policy.timeout_seconds,
                )
                futures.append(
                    executor.submit(
                        call_with_retries, ask_jev, "jev_rerank", classify_jev_error, policy
                    )
                )
            # Read in document order, so the relevances line up whatever order the calls end in.
            try:
                for future in futures:
                    relevances.append(future.result().nouls[QUESTION_NAME].noul)
            except Exception:
                # Calls not sent yet are dropped; leaving the block waits for those in flight.
                executor.shutdown(cancel_futures=True)
                raise
        duration_ms = (time.perf_counter() - started) * 1000

        logger.info(
            "jev_reranked documents=%d parallel=%d duration_ms=%d",
            len(documents),
            parallel,
            duration_ms,
        )
        return relevances


def build_jev_client(api_key: str) -> TypeSafeClient:
    """Build the TypeSafe client the Jev reranker calls through.

    Args:
        api_key: The TypeSafe API key.

    Returns:
        A client with the SDK's own retries off. Never raises for a well-formed key.

    Raises:
        typesafe_sdk.TypeSafeError: The key is empty or malformed.
    """
    return TypeSafeClient(api_key=api_key, retry=TypeSafeRetryPolicy(max_retries=0))
