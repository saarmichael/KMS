from typing import Literal

import pytest

from kms.ai import set_embedder
from kms.ai.interfaces import Embedder
from kms.ai.noop import NoOpReranker
from kms.search import MatchKind
from kms.search.service import (
    FoundAsset,
    MatchSnippet,
    build_snippet,
    embed_query,
    mark_closest_sentences,
    normalise_query,
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
    return FoundAsset(asset={}, score=1.0, snippet=snippet, match=match)


def unit_row(kind: str, body: str | None = None, start_char=None, end_char=None) -> dict:
    """An asset row with its best unit's columns, as the search's final fetch returns it."""
    return {
        "filename": "notes-lisbon.txt",
        "description": "Notes from a trip to Lisbon.",
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


def test_snippet_filename_uses_filename():
    snippet = build_snippet(unit_row("filename", body="notes-lisbon.txt notes lisbon txt"))

    assert snippet.kind == "filename"
    assert snippet.text == "notes-lisbon.txt"
    assert (snippet.start_char, snippet.end_char) == (None, None)


def test_noop_reranker_keeps_order():
    assert NoOpReranker().rerank("lisbon", ["c", "a", "b"]) == [0, 1, 2]


def test_closest_sentence_marked_on_semantic_passage(use_embedder):
    use_embedder(SentenceEmbedder({"A small bakery sells custard tarts.": [1.0, 0.0]}))

    [result] = mark_closest_sentences(QUERY_VECTOR, [found_asset(MatchKind.SEMANTIC)])

    # The second sentence starts 26 characters into the passage, which starts at 100.
    assert (result.snippet.sentence_start_char, result.snippet.sentence_end_char) == (126, 161)
    assert result.snippet.start_char == 100


def test_exact_and_partial_results_get_no_sentence(use_embedder):
    embedder = SentenceEmbedder({})
    use_embedder(embedder)
    found = [found_asset(MatchKind.EXACT), found_asset(MatchKind.PARTIAL)]

    results = mark_closest_sentences(QUERY_VECTOR, found)

    assert results == found
    assert embedder.calls == []


@pytest.mark.parametrize("kind", ["metadata", "image", "filename"])
def test_non_content_snippet_gets_no_sentence(use_embedder, kind):
    use_embedder(SentenceEmbedder({}))
    found = [found_asset(MatchKind.SEMANTIC, kind=kind, text="Notes from a trip to Lisbon.")]

    [result] = mark_closest_sentences(QUERY_VECTOR, found)

    assert (result.snippet.sentence_start_char, result.snippet.sentence_end_char) == (None, None)


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
    assert results[0].snippet.sentence_start_char is not None
    assert results[1].snippet.sentence_start_char is None
    assert results[2].snippet.sentence_start_char is not None


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
