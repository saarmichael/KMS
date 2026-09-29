"""One search: both paths at once, fused into assets, the top ones scored by the reranker, one
page of them with a snippet each."""

import logging
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.engine import RowMapping

from kms.ai import get_embedder, get_reranker
from kms.ai.errors import INTERACTIVE_POLICY, OPTIONAL_POLICY
from kms.config import get_settings
from kms.db import get_engine
from kms.models import assets, search_units
from kms.search import MatchKind, UnitHit
from kms.search.fuse import AssetMatch, fuse_units, group_by_asset
from kms.search.keyword import keyword_search
from kms.search.order import SearchOrder, filter_matches, filter_units, order_matches
from kms.search.sentences import cosine_similarity, split_sentences
from kms.search.vector import vector_search

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MatchSnippet:
    """Why an asset matched: the part of it that matched best.

    Attributes:
        kind: "metadata", "content", "image", "visible_text" or "filename".
        text: The passage for "content", the description for "metadata" and "image", the text
            read from the image for "visible_text", the filename for "filename".
        start_char: Where the passage starts in the file; only for "content".
        end_char: Where the passage ends in the file; only for "content".
        sentence_start: Where the sentence of `text` closest in meaning to the query starts,
            counted in `text`; only for an asset matched by meaning.
        sentence_end: Where that sentence ends, counted in `text`.
    """

    kind: str
    text: str
    start_char: int | None
    end_char: int | None
    sentence_start: int | None
    sentence_end: int | None


@dataclass(frozen=True)
class FoundAsset:
    """One asset on a page of results.

    Attributes:
        asset: The asset's row, with its best unit's columns alongside.
        score: 1.0 for the best asset of the whole query, less for the rest.
        snippet: Why it matched.
        match: How it matched: exact, partial or semantic.
        relevance: How well it answers the query, from 0 to 1, as the reranker judged it; None
            when it was not scored.
    """

    asset: RowMapping
    score: float
    snippet: MatchSnippet
    match: MatchKind
    relevance: float | None


@dataclass(frozen=True)
class ResultPage:
    """One page of search results.

    Attributes:
        results: The page's assets, best first.
        has_more: True when a next page holds more assets.
    """

    results: list[FoundAsset]
    has_more: bool


class QueryEmbeddingFailed(Exception):
    """The embedding service did not answer for the query, so the search cannot run."""


def normalise_query(query: str) -> str:
    """Trim the query and collapse each run of whitespace to one space; case is kept, so the
    text embedded is exactly what was typed. Never raises."""
    return re.sub(r"\s+", " ", query).strip()


# The size is read once, at import.
@lru_cache(maxsize=get_settings().query_cache_size)
def embed_query(model: str, query: str) -> tuple[float, ...]:
    """Embed a search query, remembering the vectors of recent queries.

    Embedding is the one vendor call in a search, so a repeated query skips it. The same text
    always gives the same vector, so a remembered one is never stale.

    Args:
        model: The embedder's model. Not passed on; it is here so that it is part of the
            cache key, and a vector of one model is never reused for another.
        query: The normalised query.

    Returns:
        The query's vector. A tuple, because the cache hands the same object to every caller
        and a list could be changed by one of them.

    Raises:
        QueryEmbeddingFailed: The embedder raised, whatever the reason; its error is chained as
            the cause. A failed call is not remembered.
    """
    # A search cannot run without its query's vector, so the call gets one quick retry.
    try:
        vectors = get_embedder().embed([query], "query", INTERACTIVE_POLICY)
    except Exception as error:
        raise QueryEmbeddingFailed(str(error)) from error
    return tuple(vectors[0])


# Each (rerank model, query, text) scored so far, the most recently used last. A text's relevance
# depends only on the query, not on the other results, so it holds whatever the order or filter.
relevance_cache: OrderedDict[tuple[str, str, str], float] = OrderedDict()
# Searches run on several threads at once, and the cache must not change while one of them reads it.
relevance_cache_lock = threading.Lock()


def rerank_with_cache(query: str, documents: list[str]) -> list[float] | None:
    """Score each document against the query, asking the reranker only about texts not scored
    before.

    Args:
        query: The normalised query.
        documents: One text per result.

    Returns:
        One relevance per document, in the order of `documents`; None when the reranker gives no
        relevance. At most RERANK_CACHE_SIZE scores are kept; the least recently used goes first.

    Raises:
        Exception: A vendor error, raised as it comes; nothing from the failed call is kept.
    """
    settings = get_settings()
    model = settings.rerank_model

    unseen = []
    with relevance_cache_lock:
        for text in documents:
            if (model, query, text) not in relevance_cache and text not in unseen:
                unseen.append(text)

    # The call is made outside the lock, so other searches are not held up by it.
    if unseen:
        # Relevance only adds to results the user already has, so it is never waited for.
        relevances = get_reranker().rerank(query, unseen, OPTIONAL_POLICY)
        if relevances is None:
            return None
        with relevance_cache_lock:
            for text, relevance in zip(unseen, relevances, strict=True):
                relevance_cache[(model, query, text)] = relevance

    with relevance_cache_lock:
        found_relevances = []
        for text in documents:
            key = (model, query, text)
            found_relevances.append(relevance_cache[key])
            relevance_cache.move_to_end(key)
        while len(relevance_cache) > settings.rerank_cache_size:
            relevance_cache.popitem(last=False)
    return found_relevances


def build_snippet(row: RowMapping) -> MatchSnippet:
    """Build the snippet from an asset's row and its best unit's columns.

    Args:
        row: The asset's columns plus `unit_kind`, `unit_body`, `unit_start_char` and
            `unit_end_char`.

    Returns:
        The passage and its offsets for a content unit; otherwise the text that stands for
        the unit, with no offsets. No sentence yet: `mark_closest_sentences` adds it.

    Raises:
        ValueError: The unit is of a kind the worker never writes.
    """
    kind = row["unit_kind"]
    if kind == "content":
        return MatchSnippet(
            kind, row["unit_body"], row["unit_start_char"], row["unit_end_char"], None, None
        )
    # An image unit has no text, so it shows the description.
    if kind in ("metadata", "image"):
        return MatchSnippet(kind, row["description"], None, None, None, None)
    if kind == "visible_text":
        return MatchSnippet(kind, row["visible_text"], None, None, None, None)
    if kind == "filename":
        return MatchSnippet(kind, row["filename"], None, None, None, None)
    raise ValueError(f"unknown unit kind: {kind}")


def run_both_paths(
    collection: str, query: str, model: str, limit: int
) -> tuple[list[UnitHit], list[UnitHit]]:
    """Run the keyword path and the vector path at the same time.

    Args:
        collection: The collection to search in.
        query: The normalised query.
        model: The embedder's model, for the query vector and the units it is compared with.
        limit: The most units each path returns.

    Returns:
        The keyword hits, then the vector hits, each best first.

    Raises:
        QueryEmbeddingFailed: The query could not be embedded.
        Exception: A database error from either path, raised as it comes.
    """
    # Keyword runs while the query is embedded. A pool per call, so searches don't queue.
    with ThreadPoolExecutor(max_workers=2) as executor:
        keyword_future = executor.submit(keyword_search, collection, query, limit)
        # Embed, then vector search, on one thread.
        vector_future = executor.submit(
            lambda: vector_search(collection, list(embed_query(model, query)), model, limit)
        )
        keyword_hits = keyword_future.result()
        vector_hits = vector_future.result()
    return keyword_hits, vector_hits


def fetch_found_assets(page_matches: list[AssetMatch]) -> list[FoundAsset]:
    """Load the rows of some matches in one query and give each its snippet.

    Args:
        page_matches: The matches to load (a page, or the top results and the page), best first.

    Returns:
        One FoundAsset per match whose asset still exists, in the order of `page_matches`.
        Empty when `page_matches` is empty.

    Raises:
        Exception: A database error, raised as it comes.
    """
    if not page_matches:
        return []

    # Each asset with its best unit, for the snippet.
    best_unit_ids = [match.unit_id for match in page_matches]
    rows_query = (
        select(
            assets,
            search_units.c.kind.label("unit_kind"),
            search_units.c.body.label("unit_body"),
            search_units.c.start_char.label("unit_start_char"),
            search_units.c.end_char.label("unit_end_char"),
        )
        .join(search_units, search_units.c.asset_id == assets.c.id)
        .where(search_units.c.id.in_(best_unit_ids))
    )
    with get_engine().connect() as connection:
        rows = connection.execute(rows_query).mappings().all()
    rows_by_asset = {row["id"]: row for row in rows}

    found = []
    for match in page_matches:
        row = rows_by_asset.get(match.asset_id)
        # Deleted since the search.
        if row is None:
            continue
        found.append(
            FoundAsset(
                asset=row,
                score=match.score,
                snippet=build_snippet(row),
                match=match.match,
                relevance=None,
            )
        )
    return found


def mark_closest_sentences(
    query_vector: Sequence[float], found: list[FoundAsset]
) -> list[FoundAsset]:
    """Point each snippet matched by meaning at its sentence closest to the query.

    A snippet matched by meaning may share no word with the query, so nothing in it can be
    marked; its closest sentence shows the user where the meaning is. The sentences are
    embedded by the same model that ranked the asset, so the sentence reflects why it ranked.
    Every kind of snippet is treated alike: its `text` is split, whether a passage, a
    description or a file name (which comes out as one sentence).

    Args:
        query_vector: The query's vector.
        found: The page's assets, in their final order.

    Returns:
        The same assets in the same order. Each one matched by meaning has its closest
        sentence's offsets in its snippet's `text` set; the rest are unchanged. On a vendor
        error, `found` unchanged: the sentence only adds to results the user already has, so
        it never fails the search.
    """
    # Each asset matched by meaning, by its place on the page, with its snippet's sentences.
    sentences_by_place = {}
    for place, found_asset in enumerate(found):
        if found_asset.match == MatchKind.SEMANTIC:
            sentences = split_sentences(found_asset.snippet.text)
            if sentences:
                sentences_by_place[place] = sentences
    if not sentences_by_place:
        return found

    # Every sentence of the page in one call. Sentences are stored text, like the units they
    # come from, so they are embedded as documents.
    sentence_texts = []
    for sentences in sentences_by_place.values():
        for sentence in sentences:
            sentence_texts.append(sentence.text)
    try:
        # The sentence only adds to results the user already has, so it is never waited for.
        vectors = get_embedder().embed(sentence_texts, "document", OPTIONAL_POLICY)
    except Exception as error:
        logger.warning("sentence_match_failed error=%s", type(error).__name__)
        return found

    # The vectors come back in the order the sentences were sent.
    marked = list(found)
    next_vector = 0
    for place, sentences in sentences_by_place.items():
        closest = sentences[0]
        closest_similarity = -1.0
        for sentence in sentences:
            similarity = cosine_similarity(query_vector, vectors[next_vector])
            next_vector += 1
            if similarity > closest_similarity:
                closest = sentence
                closest_similarity = similarity

        snippet = replace(
            found[place].snippet, sentence_start=closest.start, sentence_end=closest.end
        )
        marked[place] = replace(found[place], snippet=snippet)
    return marked


def score_relevance(query: str, found: list[FoundAsset], order: SearchOrder) -> list[FoundAsset]:
    """Give each result the reranker's relevance, judged on its snippet's text.

    Args:
        query: The normalised query.
        found: The results to score, in the chosen order.
        order: The order the user chose; only RELEVANCE is sorted here.

    Returns:
        The same results with `relevance` set: by relevance, highest first, for RELEVANCE (equal
        ones keep their order); in their order for any other. `found` unchanged when the
        reranker gives no relevance, and on a vendor error: relevance only adds to results the
        user already has, so it never fails the search.
    """
    texts = [found_asset.snippet.text for found_asset in found]
    try:
        relevances = rerank_with_cache(query, texts)
    except Exception as error:
        logger.warning("rerank_failed error=%s", type(error).__name__)
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


def search(
    collection: str,
    query: str,
    page: int,
    order: SearchOrder,
    match_kinds: list[MatchKind] | None,
    asset_types: list[str] | None,
    unit_kinds: list[str] | None,
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

    Returns:
        The page's assets with their scores, relevances and snippets. Empty, with `has_more`
        false, when nothing matches or the page is past the end.

    Raises:
        QueryEmbeddingFailed: The query could not be embedded.
        Exception: A database error, raised as it comes.
    """
    started = time.perf_counter()
    settings = get_settings()

    # Normalise the query.
    query = normalise_query(query)
    model = get_embedder().model

    # Search both paths.
    keyword_hits, vector_hits = run_both_paths(collection, query, model, settings.units_per_path)

    # Fuse. Scores are measured against the best unit before filtering, so a filter never
    # changes the scores of what it keeps.
    units = fuse_units(keyword_hits, vector_hits)
    top_score = units[0].score if units else 1.0

    # Filter, group into assets, order, cap. The cap comes last, so a filter can reach an
    # asset that is far down the unfiltered list.
    units = filter_units(units, asset_types, unit_kinds)
    matches = group_by_asset(units, top_score)
    matches = filter_matches(matches, match_kinds)
    matches = order_matches(matches, order)
    matches = matches[: settings.max_assets_per_query]

    # Slice the page.
    page_start = (page - 1) * settings.page_size
    page_end = page * settings.page_size
    page_matches = matches[page_start:page_end]
    has_more = len(matches) > page_end

    # Load rows and snippets. A page that starts among the top results needs all of them, scored
    # together, because in the relevance order any of them may land on it.
    candidate_count = settings.rerank_candidates
    reranked = 0
    if page_start < candidate_count:
        fetched = fetch_found_assets(matches[: max(candidate_count, page_end)])
        candidates = score_relevance(query, fetched[:candidate_count], order)
        for candidate in candidates:
            if candidate.relevance is not None:
                reranked += 1
        results = (candidates + fetched[candidate_count:])[page_start:page_end]
    else:
        results = fetch_found_assets(page_matches)

    # Point the passages matched by meaning at their closest sentence. The query vector is
    # already cached, so this asks the embedder only for the sentences.
    results = mark_closest_sentences(embed_query(model, query), results)
    sentence_count = 0
    for result in results:
        if result.snippet.sentence_start is not None:
            sentence_count += 1

    logger.info(
        "search_done collection=%s units_keyword=%s units_vector=%s assets=%s reranked=%s "
        "sentences=%s ms=%s",
        collection,
        len(keyword_hits),
        len(vector_hits),
        len(matches),
        reranked,
        sentence_count,
        round((time.perf_counter() - started) * 1000, 1),
    )
    return ResultPage(results=results, has_more=has_more)
