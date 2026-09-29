from types import SimpleNamespace

import pytest

from kms.ai.voyage import VoyageReranker

MODEL = "rerank-test-model"


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

    relevances = VoyageReranker(client, MODEL).rerank("lisbon", ["a", "b", "c"])

    assert relevances == [0.2, 0.9, 0.5]
    (call,) = client.calls
    assert call["query"] == "lisbon"
    assert call["documents"] == ["a", "b", "c"]
    assert call["model"] == MODEL
    assert call["truncation"] is True


def test_no_documents_makes_no_call():
    client = StubClient([])

    assert VoyageReranker(client, MODEL).rerank("lisbon", []) == []
    assert client.calls == []


def test_wrong_count_raises():
    client = StubClient([0.2])

    with pytest.raises(ValueError, match="1 scores for 2 documents"):
        VoyageReranker(client, MODEL).rerank("lisbon", ["a", "b"])
