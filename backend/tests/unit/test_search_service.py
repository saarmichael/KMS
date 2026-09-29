from typing import Literal

import pytest

from kms.ai import set_embedder
from kms.ai.interfaces import Embedder, Reranker
from kms.ai.noop import NoOpReranker
from kms.config import get_settings
from kms.search import MatchKind, service
from kms.search.order import SearchOrder
from kms.search.service import (
    FoundAsset,
    MatchSnippet,
    build_snippet,
    embed_query,
    mark_closest_sentences,
    normalise_query,
    relevance_cache,
    rerank_with_cache,
    score_relevance,
)


class CountingEmbedder(Embedder):
    """Returns a fixed vector and remembers every query it was asked to embed."""

    model = "counting-embedder"

    def __init__(self):
        self.queries: list[str | bytes] = []

    def embed(
        self, inputs: list[str | bytes], input_type: Literal["document", "query"]
    ) -> list[list[float]]:
        self.queries.extend(inputs)
        return [[1.0, 0.0] for _ in inputs]


@pytest.fixture
def counting_embedder():
    # The cache outlives a test, so it is emptied on the way in and on the way out.
    embedder = CountingEmbedder()
    set_embedder(embedder)
    embed_query.cache_clear()
    yield embedder
    embed_query.cache_clear()
    set_embedder(None)


class SentenceEmbedder(Embedder):
    """Embeds each text as the vector a test gave it, along axis 1 when it gave none, and
    remembers every call."""

    model = "sentence-embedder"

    def __init__(self, vectors_by_text: dict[str, list[float]]):
        self.vectors_by_text = vectors_by_text
        self.calls: list[list[str | bytes]] = []

    def embed(
        self, inputs: list[str | bytes], input_type: Literal["document", "query"]
    ) -> list[list[float]]:
        self.calls.append(inputs)
        return [self.vectors_by_text.get(text, [0.0, 1.0]) for text in inputs]


class FailingEmbedder(Embedder):
    """Fails every call, as a vendor outage would."""

    model = "failing-embedder"

    def embed(
        self, inputs: list[str | bytes], input_type: Literal["document", "query"]
    ) -> list[list[float]]:
        raise ConnectionError("vendor down")


@pytest.fixture
def use_embedder():
    # Sets the embedder a test builds, and takes it away after the test.
    yield set_embedder
    set_embedder(None)


# Along axis 0, the direction of the query in these tests.
QUERY_VECTOR = [1.0, 0.0]
PASSAGE = "The tram climbs the hill. A small bakery sells custard tarts."


def found_asset(match: MatchKind, kind: str = "content", text: str = PASSAGE) -> FoundAsset:
    """One result on a page, its passage at offset 100 in the file."""
    if kind == "content":
        snippet = MatchSnippet(kind, text, 100, 100 + len(text), None, None)
    else:
        snippet = MatchSnippet(kind, text, None, None, None, None)
    return FoundAsset(asset={}, score=1.0, snippet=snippet, match=match, relevance=None)


def unit_row(kind: str, body: str | None = None, start_char=None, end_char=None) -> dict:
    """An asset row with its best unit's columns, as the search's final fetch returns it."""
    return {
        "filename": "notes-lisbon.txt",
        "description": "Notes from a trip to Lisbon.",
        "visible_text": "TRAM 28 Lisboa",
        "unit_kind": kind,
        "unit_body": body,
        "unit_start_char": start_char,
        "unit_end_char": end_char,
    }


def test_normalise_trims_and_collapses_whitespace():
    assert normalise_query("  black \t hair\n\nin   Lisbon ") == "black hair in Lisbon"


def test_normalise_keeps_case():
    assert normalise_query("Lisbon NOTES") == "Lisbon NOTES"


def test_embed_query_calls_embedder_once_for_repeated_query(counting_embedder):
    first = embed_query("counting-embedder", normalise_query("black hair"))
    second = embed_query("counting-embedder", normalise_query("  black   hair "))

    assert first == second == (1.0, 0.0)
    assert counting_embedder.queries == ["black hair"]


def test_embed_query_keys_on_model(counting_embedder):
    embed_query("model-a", "black hair")
    embed_query("model-b", "black hair")

    assert counting_embedder.queries == ["black hair", "black hair"]


def test_snippet_content_has_chunk_text_and_offsets():
    row = unit_row("content", body="her black hair tied back", start_char=1204, end_char=1228)

    snippet = build_snippet(row)

    assert snippet.kind == "content"
    assert snippet.text == "her black hair tied back"
    assert (snippet.start_char, snippet.end_char) == (1204, 1228)


@pytest.mark.parametrize("kind", ["metadata", "image"])
def test_snippet_metadata_and_image_use_description(kind):
    snippet = build_snippet(unit_row(kind, body="lisbon trip notes"))

    assert snippet.kind == kind
    assert snippet.text == "Notes from a trip to Lisbon."
    assert (snippet.start_char, snippet.end_char) == (None, None)


def test_visible_text_snippet_is_the_image_text():
    snippet = build_snippet(unit_row("visible_text", body="TRAM 28 Lisboa"))

    assert snippet.kind == "visible_text"
    assert snippet.text == "TRAM 28 Lisboa"
    assert (snippet.start_char, snippet.end_char) == (None, None)


def test_snippet_filename_uses_filename():
    snippet = build_snippet(unit_row("filename", body="notes-lisbon.txt notes lisbon txt"))

    assert snippet.kind == "filename"
    assert snippet.text == "notes-lisbon.txt"
    assert (snippet.start_char, snippet.end_char) == (None, None)


class StubReranker(Reranker):
    """Scores each text with the relevance a test gave it, 0.5 when it gave none, and remembers
    every call."""

    def __init__(self, relevance_by_text: dict[str, float] | None = None):
        self.relevance_by_text = relevance_by_text or {}
        self.calls: list[list[str]] = []

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        self.calls.append(documents)
        return [self.relevance_by_text.get(text, 0.5) for text in documents]


class FailingReranker(Reranker):
    """Fails every call, as a vendor outage would."""

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        raise ConnectionError("vendor down")


@pytest.fixture
def use_reranker(monkeypatch):
    # Puts in the reranker a test builds. The cache outlives a test, so it is emptied on the way
    # in and on the way out.
    relevance_cache.clear()
    yield lambda reranker: monkeypatch.setattr(service, "get_reranker", lambda: reranker)
    relevance_cache.clear()


def texts(found: list[FoundAsset]) -> list[str]:
    return [found_asset.snippet.text for found_asset in found]


def page_of(*snippet_texts: str) -> list[FoundAsset]:
    """Results in score order, each with its own snippet text; they match in every way."""
    kinds = [MatchKind.EXACT, MatchKind.PARTIAL, MatchKind.SEMANTIC]
    found = []
    for position, text in enumerate(snippet_texts):
        found.append(found_asset(kinds[position % 3], kind="metadata", text=text))
    return found


def test_noop_reranker_gives_no_relevance(use_reranker):
    use_reranker(NoOpReranker())
    found = page_of("tram", "bakery")

    results = score_relevance("lisbon", found, SearchOrder.RELEVANCE)

    assert results == found
    assert [result.relevance for result in results] == [None, None]


def test_relevance_order_sorts_candidates_by_relevance(use_reranker):
    use_reranker(StubReranker({"tram": 0.2, "bakery": 0.9, "river": 0.6}))

    results = score_relevance("lisbon", page_of("tram", "bakery", "river"), SearchOrder.RELEVANCE)

    assert texts(results) == ["bakery", "river", "tram"]
    assert [result.relevance for result in results] == [0.9, 0.6, 0.2]


OTHER_ORDERS = [SearchOrder.EXACT_FIRST, SearchOrder.TIERED, SearchOrder.BLENDED]


@pytest.mark.parametrize("order", OTHER_ORDERS)
def test_other_orders_keep_order_with_relevance(use_reranker, order):
    use_reranker(StubReranker({"tram": 0.2, "bakery": 0.9, "river": 0.6}))

    results = score_relevance("lisbon", page_of("tram", "bakery", "river"), order)

    assert texts(results) == ["tram", "bakery", "river"]
    assert [result.relevance for result in results] == [0.2, 0.9, 0.6]


def test_reranker_reads_snippet_text(use_reranker):
    reranker = StubReranker()
    use_reranker(reranker)
    found = [
        found_asset(MatchKind.EXACT, kind="content", text="A passage about trams."),
        found_asset(MatchKind.SEMANTIC, kind="filename", text="notes-lisbon.txt"),
    ]

    score_relevance("lisbon", found, SearchOrder.RELEVANCE)

    assert reranker.calls == [["A passage about trams.", "notes-lisbon.txt"]]


def test_rerank_error_leaves_score_order(use_reranker):
    use_reranker(FailingReranker())
    found = page_of("tram", "bakery")

    results = score_relevance("lisbon", found, SearchOrder.RELEVANCE)

    assert results == found


def test_switching_order_makes_no_second_rerank_call(use_reranker):
    reranker = StubReranker()
    use_reranker(reranker)
    found = page_of("tram", "bakery", "river")

    score_relevance("lisbon", found, SearchOrder.RELEVANCE)
    score_relevance("lisbon", list(reversed(found)), SearchOrder.EXACT_FIRST)

    assert len(reranker.calls) == 1


def test_only_unseen_texts_are_sent(use_reranker):
    reranker = StubReranker({"tram": 0.2, "bakery": 0.9, "river": 0.6})
    use_reranker(reranker)

    rerank_with_cache("lisbon", ["tram", "bakery"])
    relevances = rerank_with_cache("lisbon", ["bakery", "river", "tram"])

    assert reranker.calls == [["tram", "bakery"], ["river"]]
    assert relevances == [0.9, 0.6, 0.2]


def test_cache_drops_least_recently_used_pair(use_reranker, monkeypatch):
    monkeypatch.setenv("RERANK_CACHE_SIZE", "2")
    get_settings.cache_clear()
    reranker = StubReranker()
    use_reranker(reranker)

    rerank_with_cache("lisbon", ["tram", "bakery"])
    # Using "tram" again makes "bakery" the least recently used, so "river" pushes it out.
    rerank_with_cache("lisbon", ["tram"])
    rerank_with_cache("lisbon", ["river"])
    rerank_with_cache("lisbon", ["tram", "bakery"])
    get_settings.cache_clear()

    assert reranker.calls == [["tram", "bakery"], ["river"], ["bakery"]]


def test_closest_sentence_marked_on_semantic_passage(use_embedder):
    use_embedder(SentenceEmbedder({"A small bakery sells custard tarts.": [1.0, 0.0]}))

    [result] = mark_closest_sentences(QUERY_VECTOR, [found_asset(MatchKind.SEMANTIC)])

    # The second sentence starts 26 characters into the passage, whatever the passage's place in
    # the file.
    assert (result.snippet.sentence_start, result.snippet.sentence_end) == (26, 61)
    assert result.snippet.start_char == 100


def test_exact_and_partial_results_get_no_sentence(use_embedder):
    embedder = SentenceEmbedder({})
    use_embedder(embedder)
    found = [found_asset(MatchKind.EXACT), found_asset(MatchKind.PARTIAL)]

    results = mark_closest_sentences(QUERY_VECTOR, found)

    assert results == found
    assert embedder.calls == []


@pytest.mark.parametrize("kind", ["metadata", "image"])
def test_description_snippet_gets_a_sentence(use_embedder, kind):
    description = "A trip to Lisbon. Custard tarts at a small bakery."
    use_embedder(SentenceEmbedder({"Custard tarts at a small bakery.": [1.0, 0.0]}))
    found = [found_asset(MatchKind.SEMANTIC, kind=kind, text=description)]

    [result] = mark_closest_sentences(QUERY_VECTOR, found)

    assert (result.snippet.sentence_start, result.snippet.sentence_end) == (18, len(description))


def test_filename_snippet_is_one_sentence(use_embedder):
    use_embedder(SentenceEmbedder({}))
    found = [found_asset(MatchKind.SEMANTIC, kind="filename", text="notes-lisbon.txt")]

    [result] = mark_closest_sentences(QUERY_VECTOR, found)

    assert (result.snippet.sentence_start, result.snippet.sentence_end) == (0, 16)


def test_one_embed_call_for_the_whole_page(use_embedder):
    embedder = SentenceEmbedder({})
    use_embedder(embedder)
    found = [
        found_asset(MatchKind.SEMANTIC),
        found_asset(MatchKind.EXACT),
        found_asset(MatchKind.SEMANTIC, text="Rain all day. We stayed in."),
    ]

    results = mark_closest_sentences(QUERY_VECTOR, found)

    assert len(embedder.calls) == 1
    assert len(embedder.calls[0]) == 4
    assert results[0].snippet.sentence_start is not None
    assert results[1].snippet.sentence_start is None
    assert results[2].snippet.sentence_start is not None


def test_no_call_when_no_result_qualifies(use_embedder):
    embedder = SentenceEmbedder({})
    use_embedder(embedder)

    mark_closest_sentences(QUERY_VECTOR, [found_asset(MatchKind.EXACT)])
    mark_closest_sentences(QUERY_VECTOR, [])

    assert embedder.calls == []


def test_embed_error_leaves_results_without_sentence(use_embedder):
    use_embedder(FailingEmbedder())
    found = [found_asset(MatchKind.SEMANTIC)]

    results = mark_closest_sentences(QUERY_VECTOR, found)

    assert results == found
