from types import SimpleNamespace

import pytest

from kms.ai.errors import OPTIONAL_POLICY
from kms.ai.voyage import VoyageReranker

MODEL = "rerank-test-model"


class StubClients:
    """Stands in for VoyageClients: hands out one stub client whatever the timeout."""

    def __init__(self, client):
        self.client = client

    def for_timeout(self, seconds: float):
        return self.client


class StubClient:
    """Stands in for voyageai.Client: records each rerank call and answers, best first as Voyage
    does, with the relevances a test gave, one per document in input order."""

    def __init__(self, relevances: list[float]):
        self.relevances = relevances
        self.calls = []

    def rerank(self, **kwargs):
        self.calls.append(kwargs)
        results = []
        for index, relevance in enumerate(self.relevances):
            results.append(SimpleNamespace(index=index, relevance_score=relevance))
        results.sort(key=lambda result: -result.relevance_score)
        return SimpleNamespace(results=results)


def test_relevance_comes_back_in_input_order():
    client = StubClient([0.2, 0.9, 0.5])

    relevances = VoyageReranker(StubClients(client), MODEL).rerank(
        "lisbon", ["a", "b", "c"], OPTIONAL_POLICY
    )

    assert relevances == [0.2, 0.9, 0.5]
    (call,) = client.calls
    assert call["query"] == "lisbon"
    assert call["documents"] == ["a", "b", "c"]
    assert call["model"] == MODEL
    assert call["truncation"] is True


def test_no_documents_makes_no_call():
    client = StubClient([])

    reranker = VoyageReranker(StubClients(client), MODEL)

    assert reranker.rerank("lisbon", [], OPTIONAL_POLICY) == []
    assert client.calls == []


def test_wrong_count_raises():
    client = StubClient([0.2])

    with pytest.raises(ValueError, match="1 scores for 2 documents"):
        VoyageReranker(StubClients(client), MODEL).rerank("lisbon", ["a", "b"], OPTIONAL_POLICY)
