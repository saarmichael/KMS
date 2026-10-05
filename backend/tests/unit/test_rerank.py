import pytest

from kms.ai import set_reranker
from kms.ai.errors import OPTIONAL_POLICY, RetryPolicy
from kms.ai.interfaces import RerankDocument, Reranker
from kms.ai.noop import NoOpReranker
from kms.config import get_settings
from kms.search import MatchKind
from kms.search.order import SearchOrder
from kms.search.rerank import (
    AllResults,
    TopResults,
    get_reranking,
    relevance_cache,
    rerank_document,
    rerank_with_cache,
    score_relevance,
)
from kms.search.service import FoundAsset, MatchSnippet


class StubReranker(Reranker):
    """Scores each document by the relevance a test gave its text, 0.5 when it gave none, and
    remembers every call's texts and its policy."""

    def __init__(self, relevance_by_text: dict[str, float] | None = None, model: str = "stub"):
        self.relevance_by_text = relevance_by_text or {}
        self.model = model
        self.calls: list[list[str]] = []
        self.policies: list[RetryPolicy] = []

    def rerank(
        self, query: str, documents: list[RerankDocument], policy: RetryPolicy
    ) -> list[float]:
        self.calls.append([document.text for document in documents])
        self.policies.append(policy)
        return [self.relevance_by_text.get(document.text, 0.5) for document in documents]


class FailingReranker(Reranker):
    """Fails every call, as a vendor outage would."""

    model = "failing"

    def rerank(
        self, query: str, documents: list[RerankDocument], policy: RetryPolicy
    ) -> list[float]:
        raise ConnectionError("vendor down")


@pytest.fixture(autouse=True)
def empty_cache():
    # The cache outlives a test, so it is emptied on the way in and on the way out.
    relevance_cache.clear()
    yield
    relevance_cache.clear()


def found_asset(match: MatchKind, kind: str = "metadata", text: str = "tram") -> FoundAsset:
    """One result with an asset row that has what a reranker reads."""
    asset = {"title": f"Title of {text}", "filename": f"{text}.txt", "tags": ["lisbon", "trip"]}
    snippet = MatchSnippet(kind, text, None, None, None, None)
    return FoundAsset(asset=asset, score=1.0, snippet=snippet, match=match, relevance=None)


def page_of(*snippet_texts: str) -> list[FoundAsset]:
    """Results in score order, each with its own snippet text; they match in every way."""
    kinds = [MatchKind.EXACT, MatchKind.PARTIAL, MatchKind.SEMANTIC]
    found = []
    for position, text in enumerate(snippet_texts):
        found.append(found_asset(kinds[position % 3], text=text))
    return found


def texts(found: list[FoundAsset]) -> list[str]:
    return [found_asset.snippet.text for found_asset in found]


def document(text: str) -> RerankDocument:
    return RerankDocument(text, "metadata", None, "notes.txt", ())


# --- scopes -------------------------------------------------------------------------------


def test_top_results_scores_its_count_for_a_page_among_them():
    assert TopResults(20).count_to_score(total=50, page_start=0) == 20


def test_top_results_scores_what_was_found_when_fewer():
    assert TopResults(20).count_to_score(total=7, page_start=0) == 7


def test_top_results_scores_nothing_for_a_page_past_them():
    assert TopResults(20).count_to_score(total=50, page_start=20) == 0


def test_all_results_scores_everything_on_any_page():
    assert AllResults().count_to_score(total=50, page_start=0) == 50
    assert AllResults().count_to_score(total=50, page_start=40) == 50


def test_voyage_reranks_the_top_candidates_and_jev_all(monkeypatch):
    monkeypatch.setenv("RERANK_CANDIDATES", "5")
    get_settings.cache_clear()

    voyage = get_reranking("voyage")
    jev = get_reranking("jev")
    get_settings.cache_clear()

    assert voyage.name == "voyage"
    assert voyage.scope == TopResults(5)
    assert jev.name == "jev"
    assert jev.scope == AllResults()


def test_reranking_takes_the_vendor_reranker():
    reranker = StubReranker()
    set_reranker("jev", reranker)
    try:
        assert get_reranking("jev").reranker is reranker
    finally:
        set_reranker("jev", None)


# --- documents ----------------------------------------------------------------------------


def test_document_carries_snippet_and_asset_facts():
    found = found_asset(MatchKind.SEMANTIC, kind="content", text="A passage about trams.")

    assert rerank_document(found) == RerankDocument(
        text="A passage about trams.",
        kind="content",
        title="Title of A passage about trams.",
        filename="A passage about trams..txt",
        tags=("lisbon", "trip"),
    )


def test_document_of_an_undescribed_asset_has_no_title_or_tags():
    found = found_asset(MatchKind.EXACT, kind="filename", text="notes.txt")
    found = FoundAsset(
        asset={"title": None, "filename": "notes.txt", "tags": None},
        score=1.0,
        snippet=found.snippet,
        match=found.match,
        relevance=None,
    )

    assert rerank_document(found) == RerankDocument("notes.txt", "filename", None, "notes.txt", ())


# --- scoring ------------------------------------------------------------------------------


def test_noop_reranker_gives_no_relevance():
    found = page_of("tram", "bakery")

    results = score_relevance("lisbon", found, SearchOrder.RELEVANCE, NoOpReranker())

    assert results == found
    assert [result.relevance for result in results] == [None, None]


def test_relevance_order_sorts_by_relevance():
    reranker = StubReranker({"tram": 0.2, "bakery": 0.9, "river": 0.6})

    results = score_relevance(
        "lisbon", page_of("tram", "bakery", "river"), SearchOrder.RELEVANCE, reranker
    )

    assert texts(results) == ["bakery", "river", "tram"]
    assert [result.relevance for result in results] == [0.9, 0.6, 0.2]


@pytest.mark.parametrize(
    "order", [SearchOrder.EXACT_FIRST, SearchOrder.TIERED, SearchOrder.BLENDED]
)
def test_other_orders_keep_order_with_relevance(order):
    reranker = StubReranker({"tram": 0.2, "bakery": 0.9, "river": 0.6})

    results = score_relevance("lisbon", page_of("tram", "bakery", "river"), order, reranker)

    assert texts(results) == ["tram", "bakery", "river"]
    assert [result.relevance for result in results] == [0.2, 0.9, 0.6]


def test_rerank_error_leaves_score_order():
    found = page_of("tram", "bakery")

    results = score_relevance("lisbon", found, SearchOrder.RELEVANCE, FailingReranker())

    assert results == found


def test_rerank_uses_optional_policy():
    reranker = StubReranker()

    score_relevance("lisbon", page_of("tram"), SearchOrder.RELEVANCE, reranker)

    assert reranker.policies == [OPTIONAL_POLICY]


# --- cache --------------------------------------------------------------------------------


def test_switching_order_makes_no_second_rerank_call():
    reranker = StubReranker()
    found = page_of("tram", "bakery", "river")

    score_relevance("lisbon", found, SearchOrder.RELEVANCE, reranker)
    score_relevance("lisbon", list(reversed(found)), SearchOrder.EXACT_FIRST, reranker)

    assert len(reranker.calls) == 1


def test_only_unseen_documents_are_sent():
    reranker = StubReranker({"tram": 0.2, "bakery": 0.9, "river": 0.6})

    rerank_with_cache(reranker, "lisbon", [document("tram"), document("bakery")])
    relevances = rerank_with_cache(
        reranker, "lisbon", [document("bakery"), document("river"), document("tram")]
    )

    assert reranker.calls == [["tram", "bakery"], ["river"]]
    assert relevances == [0.9, 0.6, 0.2]


def test_cache_keeps_each_model_apart():
    voyage = StubReranker({"tram": 0.3}, model="voyage-model")
    jev = StubReranker({"tram": 0.8}, model="jev-model")

    voyage_relevances = rerank_with_cache(voyage, "lisbon", [document("tram")])
    jev_relevances = rerank_with_cache(jev, "lisbon", [document("tram")])

    assert voyage_relevances == [0.3]
    assert jev_relevances == [0.8]
    assert jev.calls == [["tram"]]


def test_same_text_of_another_asset_is_scored_again():
    reranker = StubReranker()
    other_asset = RerankDocument("tram", "metadata", "Another title", "other.txt", ())

    rerank_with_cache(reranker, "lisbon", [document("tram")])
    rerank_with_cache(reranker, "lisbon", [other_asset])

    assert reranker.calls == [["tram"], ["tram"]]


def test_cache_drops_least_recently_used_pair(monkeypatch):
    monkeypatch.setenv("RERANK_CACHE_SIZE", "2")
    get_settings.cache_clear()
    reranker = StubReranker()

    rerank_with_cache(reranker, "lisbon", [document("tram"), document("bakery")])
    # Using "tram" again makes "bakery" the least recently used, so "river" pushes it out.
    rerank_with_cache(reranker, "lisbon", [document("tram")])
    rerank_with_cache(reranker, "lisbon", [document("river")])
    rerank_with_cache(reranker, "lisbon", [document("tram"), document("bakery")])
    get_settings.cache_clear()

    assert reranker.calls == [["tram", "bakery"], ["river"], ["bakery"]]
