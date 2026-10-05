"""Reranking inside a search: which reranker scores the results, which of them it scores, and the
relevances remembered between searches.

Two things vary from one reranker to the next, and each is its own piece here. The vendor is a
`Reranker` (from `kms.ai`); it only turns documents into relevances. Which results it is given is a
`RerankScope`: Voyage scores the top results of the requested order, Jev scores every result. A
`Reranking` pairs the two under the name the API takes.
"""

import logging
import threading
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, replace

from kms.ai import get_reranker
from kms.ai.errors import OPTIONAL_POLICY
from kms.ai.interfaces import RerankDocument, Reranker, RerankerName
from kms.config import get_settings
from kms.search.order import SearchOrder
from kms.search.service import FoundAsset

logger = logging.getLogger(__name__)


class RerankScope(ABC):
    """Decides which results of a search the reranker scores."""

    @abstractmethod
    def count_to_score(self, total: int, page_start: int) -> int:
        """Say how many of the leading results to score for one page.

        The scored results are always the first ones of the requested order, so that sorting
        them by relevance moves results only among themselves.

        Args:
            total: How many results the search found, after its filters and its cap.
            page_start: The place of the page's first result in the whole list, from 0.

        Returns:
            How many results, from the first, to score; 0 to score none for this page. Never
            more than `total`. Never raises.
        """


@dataclass(frozen=True)
class TopResults(RerankScope):
    """Scores the first `count` results, and only for a page that starts among them: a later page
    shows results that were never scored, in score order.

    Attributes:
        count: How many leading results are scored.
    """

    count: int

    def count_to_score(self, total: int, page_start: int) -> int:
        """Score the first `count` results while the page starts among them.

        Args:
            total: How many results the search found.
            page_start: The place of the page's first result, from 0.

        Returns:
            `count`, or `total` when fewer were found, for a page that starts before `count`;
            otherwise 0. Never raises.
        """
        if page_start >= self.count:
            return 0
        return min(self.count, total)


@dataclass(frozen=True)
class AllResults(RerankScope):
    """Scores every result the search found, whatever the page, so the relevance order runs
    through the whole list and every result shows its relevance."""

    def count_to_score(self, total: int, page_start: int) -> int:
        """Score every result.

        Args:
            total: How many results the search found.
            page_start: Not read; every page needs the whole list scored.

        Returns:
            `total`. Never raises.
        """
        return total


@dataclass(frozen=True)
class Reranking:
    """One way to rerank a search: a vendor's reranker and the results it scores.

    Attributes:
        name: The name the API takes, "voyage" or "jev".
        reranker: The vendor's reranker; NoOpReranker when that reranker is off.
        scope: Which results it scores.
    """

    name: RerankerName
    reranker: Reranker
    scope: RerankScope


def get_reranking(name: RerankerName) -> Reranking:
    """Return the reranking a search asked for by name.

    Voyage scores the top results only, because one Voyage call is charged by the tokens of
    every result in it and a page is all a user reads at first. Jev scores every result, because
    its calls go out one per result at the same time, so a hundred cost about as long as one,
    and its probabilities are worth having on every result.

    Args:
        name: "voyage" or "jev".

    Returns:
        Voyage's reranker over the first RERANK_CANDIDATES results, or Jev's over all of them.
        The reranker is NoOpReranker when that reranker is off. Never raises for a known name.
    """
    if name == "voyage":
        scope = TopResults(get_settings().rerank_candidates)
    else:
        scope = AllResults()
    return Reranking(name=name, reranker=get_reranker(name), scope=scope)


# Each (rerank model, query, document) scored so far, the most recently used last. A result is
# scored on its own, not against the other results, so its relevance holds whatever the order,
# the filter or the page.
relevance_cache: OrderedDict[tuple[str, str, RerankDocument], float] = OrderedDict()
# Searches run on several threads at once, and the cache must not change while one of them reads it.
relevance_cache_lock = threading.Lock()


def rerank_with_cache(
    reranker: Reranker, query: str, documents: list[RerankDocument]
) -> list[float] | None:
    """Score each document against the query, asking the reranker only about documents not
    scored before by the same model.

    Args:
        reranker: The reranker to ask.
        query: The normalised query.
        documents: One per result.

    Returns:
        One relevance per document, in the order of `documents`; None when the reranker gives no
        relevance. At most RERANK_CACHE_SIZE scores are kept, over every model; the least
        recently used goes first.

    Raises:
        Exception: A vendor error, raised as it comes; nothing from the failed call is kept.
    """
    model = reranker.model

    unseen = []
    with relevance_cache_lock:
        for document in documents:
            if (model, query, document) not in relevance_cache and document not in unseen:
                unseen.append(document)

    # The call is made outside the lock, so other searches are not held up by it.
    if unseen:
        # Relevance only adds to results the user already has, so it is never waited for.
        relevances = reranker.rerank(query, unseen, OPTIONAL_POLICY)
        if relevances is None:
            return None
        with relevance_cache_lock:
            for document, relevance in zip(unseen, relevances, strict=True):
                relevance_cache[(model, query, document)] = relevance

    with relevance_cache_lock:
        found_relevances = []
        for document in documents:
            key = (model, query, document)
            found_relevances.append(relevance_cache[key])
            relevance_cache.move_to_end(key)
        while len(relevance_cache) > get_settings().rerank_cache_size:
            relevance_cache.popitem(last=False)
    return found_relevances


def rerank_document(found_asset: FoundAsset) -> RerankDocument:
    """Describe one result as a reranker reads it.

    Args:
        found_asset: The result, with its asset row and snippet.

    Returns:
        The snippet's text and kind, and the asset's title, file name and tags. Never raises.
    """
    asset = found_asset.asset
    tags = asset["tags"] or []
    return RerankDocument(
        text=found_asset.snippet.text,
        kind=found_asset.snippet.kind,
        title=asset["title"],
        filename=asset["filename"],
        tags=tuple(tags),
    )


def score_relevance(
    query: str, found: list[FoundAsset], order: SearchOrder, reranker: Reranker
) -> list[FoundAsset]:
    """Give each result the reranker's relevance.

    Args:
        query: The normalised query.
        found: The results to score, in the chosen order.
        order: The order the user chose; only RELEVANCE is sorted here.
        reranker: The reranker to ask.

    Returns:
        The same results with `relevance` set: by relevance, highest first, for RELEVANCE (equal
        ones keep their order); in their order for any other. `found` unchanged when the
        reranker gives no relevance, and on a vendor error: relevance only adds to results the
        user already has, so it never fails the search.
    """
    documents = [rerank_document(found_asset) for found_asset in found]
    try:
        relevances = rerank_with_cache(reranker, query, documents)
    except Exception as error:
        logger.warning("rerank_failed model=%s error=%s", reranker.model, type(error).__name__)
        return found
    if relevances is None:
        return found

    scored = []
    for found_asset, relevance in zip(found, relevances, strict=True):
        scored.append(replace(found_asset, relevance=relevance))
    if order == SearchOrder.RELEVANCE:
        # sorted() is stable, so results of equal relevance keep their score order.
        scored = sorted(scored, key=lambda found_asset: -found_asset.relevance)
    return scored
