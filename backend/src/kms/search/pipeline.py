"""One search, as a pipeline: from the query to every match in order, then one page of them.

A `SearchPipeline` has two steps a pipeline must give and one it shares. `find` turns a request into
every matching asset, filtered, ordered and capped, before anything is loaded or scored; `rank`
turns those matches into the results of one page, in their final order. `search` runs both and
finishes the page. `HybridSearchPipeline` finds with the keyword and vector paths fused, and ranks
with whichever `Reranking` it was built with, so the reranker and the results it scores are
swapped without touching the steps around them.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from kms.ai import get_embedder
from kms.ai.interfaces import RerankerName
from kms.config import get_settings
from kms.search import MatchKind
from kms.search.fuse import AssetMatch, fuse_units, group_by_asset
from kms.search.order import SearchOrder, filter_matches, filter_units, order_matches
from kms.search.rerank import Reranking, get_reranking, score_relevance
from kms.search.service import (
    FoundAsset,
    ResultPage,
    embed_query,
    fetch_found_assets,
    mark_closest_sentences,
    normalise_query,
    run_both_paths,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchRequest:
    """What one search asks for, whatever page of it is shown.

    Attributes:
        collection: The collection to search in.
        query: The normalised query.
        order: How to order the results.
        match_kinds: Keep only assets whose strongest match is one of these; None keeps all.
        asset_types: Keep only assets of these types; None keeps all.
        unit_kinds: Keep only matches in these parts of an asset; None keeps all.
    """

    collection: str
    query: str
    order: SearchOrder
    match_kinds: list[MatchKind] | None
    asset_types: list[str] | None
    unit_kinds: list[str] | None


class SearchPipeline(ABC):
    """From a search request to one page of results."""

    @abstractmethod
    def find(self, request: SearchRequest) -> list[AssetMatch]:
        """Find every asset that matches, filtered, in the requested order and capped.

        Args:
            request: The search.

        Returns:
            The matches, without rows or relevance yet. Empty when nothing matches.

        Raises:
            QueryEmbeddingFailed: The query could not be embedded.
            Exception: A database error, raised as it comes.
        """

    @abstractmethod
    def rank(
        self, request: SearchRequest, matches: list[AssetMatch], page_start: int, page_end: int
    ) -> list[FoundAsset]:
        """Load and order the results that land on one page.

        Args:
            request: The search.
            matches: What `find` returned.
            page_start: The place of the page's first result in the whole list, from 0.
            page_end: The place just after the page's last result.

        Returns:
            The page's results, with their rows and snippets, in their final order; a relevance
            on each result that was scored.

        Raises:
            Exception: A database error, raised as it comes.
        """

    def search(self, request: SearchRequest, page: int) -> ResultPage:
        """Run the pipeline for one page, and point the page's results matched by meaning at
        their closest sentence.

        Args:
            request: The search.
            page: The page to return, from 1.

        Returns:
            The page's results. Empty, with `has_more` false, when nothing matches or the page
            is past the end.

        Raises:
            QueryEmbeddingFailed: The query could not be embedded.
            Exception: A database error, raised as it comes.
        """
        page_size = get_settings().page_size
        page_start = (page - 1) * page_size
        page_end = page * page_size

        matches = self.find(request)
        results = self.rank(request, matches, page_start, page_end)

        # The query vector is already cached, so this asks the embedder only for the sentences.
        model = get_embedder().model
        results = mark_closest_sentences(embed_query(model, request.query), results)
        return ResultPage(results=results, has_more=len(matches) > page_end)


class HybridSearchPipeline(SearchPipeline):
    """Finds with the keyword and vector paths fused; ranks with one reranking.

    Attributes:
        reranking: The reranker and the results it scores.
    """

    def __init__(self, reranking: Reranking):
        """Create the pipeline.

        Args:
            reranking: The reranker and the results it scores.
        """
        self.reranking = reranking

    def find(self, request: SearchRequest) -> list[AssetMatch]:
        """Search both paths, fuse them, filter, group into assets, order and cap.

        Scores are measured against the best unit before filtering, so a filter never changes
        the scores of what it keeps. The cap comes last, so a filter can reach an asset that is
        far down the unfiltered list.

        Args:
            request: The search.

        Returns:
            At most MAX_ASSETS_PER_QUERY matches, in the requested order; for RELEVANCE, score
            order until `rank` sorts them.

        Raises:
            QueryEmbeddingFailed: The query could not be embedded.
            Exception: A database error, raised as it comes.
        """
        settings = get_settings()
        model = get_embedder().model
        keyword_hits, vector_hits = run_both_paths(
            request.collection, request.query, model, settings.units_per_path
        )

        units = fuse_units(keyword_hits, vector_hits)
        top_score = units[0].score if units else 1.0

        units = filter_units(units, request.asset_types, request.unit_kinds)
        matches = group_by_asset(units, top_score)
        matches = filter_matches(matches, request.match_kinds)
        matches = order_matches(matches, request.order)
        matches = matches[: settings.max_assets_per_query]

        logger.info(
            "search_found collection=%s units_keyword=%s units_vector=%s assets=%s",
            request.collection,
            len(keyword_hits),
            len(vector_hits),
            len(matches),
        )
        return matches

    def rank(
        self, request: SearchRequest, matches: list[AssetMatch], page_start: int, page_end: int
    ) -> list[FoundAsset]:
        """Score the leading results the reranking's scope names, sort them by relevance for
        RELEVANCE, and slice the page.

        A page among the scored results needs all of them loaded and scored together, because in
        the relevance order any of them may land on it. The relevances are remembered, so a
        later page costs the reranker nothing.

        Args:
            request: The search.
            matches: What `find` returned.
            page_start: The place of the page's first result, from 0.
            page_end: The place just after the page's last result.

        Returns:
            The page's results in their final order. Those scored carry a relevance, unless the
            reranker is off or failed, which leaves score order.

        Raises:
            Exception: A database error, raised as it comes.
        """
        count_to_score = self.reranking.scope.count_to_score(len(matches), page_start)
        if count_to_score == 0:
            return fetch_found_assets(matches[page_start:page_end])

        fetched = fetch_found_assets(matches[: max(count_to_score, page_end)])
        scored = score_relevance(
            request.query, fetched[:count_to_score], request.order, self.reranking.reranker
        )
        return (scored + fetched[count_to_score:])[page_start:page_end]


def search(
    collection: str,
    query: str,
    page: int,
    order: SearchOrder,
    match_kinds: list[MatchKind] | None,
    asset_types: list[str] | None,
    unit_kinds: list[str] | None,
    reranker: RerankerName,
) -> ResultPage:
    """Search one collection and return one page of assets, in the chosen order.

    Args:
        collection: The collection to search in; the caller has checked its name.
        query: The query as typed; the caller has checked it is not blank.
        page: The page to return, from 1.
        order: How to order the assets.
        match_kinds: Keep only assets whose strongest match is one of these; None keeps all.
        asset_types: Keep only assets of these types; None keeps all.
        unit_kinds: Keep only matches in these parts of an asset; None keeps all.
        reranker: Which reranker gives the relevances.

    Returns:
        The page's assets with their scores, relevances and snippets. Empty, with `has_more`
        false, when nothing matches or the page is past the end.

    Raises:
        QueryEmbeddingFailed: The query could not be embedded.
        Exception: A database error, raised as it comes.
    """
    started = time.perf_counter()
    request = SearchRequest(
        collection=collection,
        query=normalise_query(query),
        order=order,
        match_kinds=match_kinds,
        asset_types=asset_types,
        unit_kinds=unit_kinds,
    )
    reranking = get_reranking(reranker)
    result_page = HybridSearchPipeline(reranking).search(request, page)

    reranked = 0
    sentences = 0
    for result in result_page.results:
        if result.relevance is not None:
            reranked += 1
        if result.snippet.sentence_start is not None:
            sentences += 1
    logger.info(
        "search_done collection=%s page=%s reranker=%s model=%s results=%s reranked=%s "
        "sentences=%s ms=%s",
        collection,
        page,
        reranking.name,
        reranking.reranker.model,
        len(result_page.results),
        reranked,
        sentences,
        round((time.perf_counter() - started) * 1000, 1),
    )
    return result_page
