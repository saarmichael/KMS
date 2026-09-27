from typing import Literal

import pytest

from kms.ai import set_embedder
from kms.ai.interfaces import Embedder
from kms.ai.noop import NoOpReranker
from kms.search.service import build_snippet, embed_query, normalise_query


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
