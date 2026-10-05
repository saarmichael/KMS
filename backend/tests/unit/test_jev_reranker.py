import threading
from types import SimpleNamespace

import httpx2
import pytest
from typesafe_sdk import (
    TypeSafeAPITimeoutError,
    TypeSafeAuthenticationError,
    TypeSafeBadRequestError,
    TypeSafeInternalServerError,
    TypeSafeRateLimitError,
)

from kms.ai.errors import OPTIONAL_POLICY
from kms.ai.interfaces import RerankDocument
from kms.ai.jev import QUESTION, QUESTION_NAME, JevReranker, classify_jev_error, jev_state

MODEL = "jev-test-model"


class StubClient:
    """Stands in for TypeSafeClient: records each system_one call and answers with the
    probability a test gave the result's matched text, 0.5 when it gave none."""

    def __init__(self, relevance_by_text: dict[str, float] | None = None, failing_text=None):
        self.relevance_by_text = relevance_by_text or {}
        self.failing_text = failing_text
        self.calls = []
        # The reranker calls from several threads at once.
        self.lock = threading.Lock()

    def system_one(self, **kwargs):
        with self.lock:
            self.calls.append(kwargs)
        text = kwargs["state"]["result"]["matched_text"]
        if text == self.failing_text:
            raise TypeSafeAuthenticationError(401, {"detail": "bad key"}, httpx2.Headers())
        answer = SimpleNamespace(noul=self.relevance_by_text.get(text, 0.5))
        return SimpleNamespace(nouls={QUESTION_NAME: answer})


def documents(*texts: str) -> list[RerankDocument]:
    return [RerankDocument(text, "content", "A title", "notes.txt", ("trip",)) for text in texts]


def test_one_call_per_document_and_relevance_in_input_order():
    client = StubClient({"a": 0.2, "b": 0.9, "c": 0.5})

    relevances = JevReranker(client, MODEL, parallel_calls=2).rerank(
        "lisbon", documents("a", "b", "c"), OPTIONAL_POLICY
    )

    assert relevances == [0.2, 0.9, 0.5]
    assert len(client.calls) == 3
    sent_texts = sorted(call["state"]["result"]["matched_text"] for call in client.calls)
    assert sent_texts == ["a", "b", "c"]


def test_each_call_asks_the_one_question_of_the_model_with_the_policy_timeout():
    client = StubClient()

    JevReranker(client, MODEL, parallel_calls=4).rerank("lisbon", documents("a"), OPTIONAL_POLICY)

    (call,) = client.calls
    assert call["questions"] == {QUESTION_NAME: QUESTION}
    assert call["model"] == MODEL
    assert call["timeout"] == OPTIONAL_POLICY.timeout_seconds
    assert call["state"] == jev_state("lisbon", documents("a")[0])


def test_no_documents_makes_no_call():
    client = StubClient()

    assert JevReranker(client, MODEL, parallel_calls=4).rerank("q", [], OPTIONAL_POLICY) == []
    assert client.calls == []


def test_one_failed_call_fails_the_rerank():
    client = StubClient(failing_text="b")

    with pytest.raises(TypeSafeAuthenticationError):
        JevReranker(client, MODEL, parallel_calls=4).rerank(
            "lisbon", documents("a", "b", "c"), OPTIONAL_POLICY
        )


def test_state_holds_query_and_result_facts():
    document = RerankDocument("Gelato in Marseille.", "metadata", "Gelato", "IMG_1.jpg", ("food",))

    assert jev_state("ice cream", document) == {
        "query": "ice cream",
        "result": {
            "title": "Gelato",
            "file_name": "IMG_1.jpg",
            "tags": ["food"],
            "matched_part": "description",
            "matched_text": "Gelato in Marseille.",
        },
    }


def test_state_of_an_undescribed_result_leaves_out_title_and_tags():
    document = RerankDocument("notes.txt", "filename", None, "notes.txt", ())

    assert jev_state("notes", document)["result"] == {
        "file_name": "notes.txt",
        "matched_part": "file name",
        "matched_text": "notes.txt",
    }


def test_rate_limit_is_retried_after_the_wait_jev_asks_for():
    error = TypeSafeRateLimitError(429, {}, httpx2.Headers({"retry-after-ms": "1500"}))

    verdict = classify_jev_error(error)

    assert verdict.retryable is True
    assert verdict.server_wait_seconds == 1.5


@pytest.mark.parametrize(
    "error",
    [
        TypeSafeInternalServerError(503, {}, httpx2.Headers()),
        TypeSafeAPITimeoutError(3.0),
    ],
)
def test_server_errors_and_timeouts_are_retried(error):
    verdict = classify_jev_error(error)

    assert verdict.retryable is True
    assert verdict.server_wait_seconds is None


@pytest.mark.parametrize(
    "error",
    [
        TypeSafeBadRequestError(
            400, {"detail": {"error_type": "max_tokens_exceeded"}}, httpx2.Headers()
        ),
        TypeSafeAuthenticationError(401, {}, httpx2.Headers()),
        ValueError("not a vendor error"),
    ],
)
def test_bad_requests_and_other_errors_are_not_retried(error):
    assert classify_jev_error(error).retryable is False
