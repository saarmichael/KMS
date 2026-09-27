"""One search: both paths at once, fused into assets, one page of them with a snippet each."""

import logging
import re
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.engine import RowMapping

from kms.ai import get_embedder, get_reranker
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
        kind: "metadata", "content", "image" or "filename".
        text: The passage for "content", the description for "metadata" and "image", the
            filename for "filename".
        start_char: Where the passage starts in the file; only for "content".
        end_char: Where the passage ends in the file; only for "content".
        sentence_start_char: Where the passage's sentence closest in meaning to the query starts
            in the file; only for "content" matched by meaning.
        sentence_end_char: Where that sentence ends in the file.
    """

    kind: str
    text: str
    start_char: int | None
    end_char: int | None
    sentence_start_char: int | None
    sentence_end_char: int | None


@dataclass(frozen=True)
class FoundAsset:
    """One asset on a page of results.

    Attributes:
        asset: The asset's row, with its best unit's columns alongside.
        score: 1.0 for the best asset of the whole query, less for the rest.
        snippet: Why it matched.
        match: How it matched: exact, partial or semantic.
    """

    asset: RowMapping
    score: float
    snippet: MatchSnippet
    match: MatchKind


@dataclass(frozen=True)
class ResultPage:
    """One page of search results.

    Attributes:
        results: The page's assets, best first.
        has_more: True when a next page holds more assets.
    """

    results: list[FoundAsset]
    has_more: bool


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
        Exception: A vendor error, raised as it comes; a failed call is not remembered.
    """
    vectors = get_embedder().embed([query], "query")
    return tuple(vectors[0])


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
        Exception: A database or vendor error from either path, raised as it comes.
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
    """Load the rows of one page of matches in one query and give each its snippet.

    Args:
        page_matches: The page's matches, best first.

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
            FoundAsset(asset=row, score=match.score, snippet=build_snippet(row), match=match.match)
        )
    return found


def mark_closest_sentences(
    query_vector: Sequence[float], found: list[FoundAsset]
) -> list[FoundAsset]:
    """Point each passage matched by meaning at its sentence closest to the query.

    A passage matched by meaning may share no word with the query, so nothing in it can be
    marked; its closest sentence shows the user where the meaning is. The sentences are
    embedded by the same model that ranked the passage, so the sentence reflects why it ranked.

    Args:
        query_vector: The query's vector.
        found: The page's assets, in their final order.

    Returns:
        The same assets in the same order. Each one matched by meaning whose snippet is a
        passage has its closest sentence's offsets set; the rest are unchanged. On a vendor
        error, `found` unchanged: the sentence only adds to results the user already has, so
        it never fails the search.
    """
    # Each qualifying asset's place on the page, with its passage's sentences.
    sentences_by_place = {}
    for place, found_asset in enumerate(found):
        if found_asset.match == MatchKind.SEMANTIC and found_asset.snippet.kind == "content":
            sentences = split_sentences(found_asset.snippet.text)
            if sentences:
                sentences_by_place[place] = sentences
    if not sentences_by_place:
        return found

    # Every sentence of the page in one call. Sentences are stored text, like the chunks they
    # come from, so they are embedded as documents.
    sentence_texts = []
    for sentences in sentences_by_place.values():
        for sentence in sentences:
            sentence_texts.append(sentence.text)
    try:
        vectors = get_embedder().embed(sentence_texts, "document")
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

        # The sentence's offsets are within the passage; the passage's start makes them the file's.
        snippet = found[place].snippet
        snippet = replace(
            snippet,
            sentence_start_char=snippet.start_char + closest.start,
            sentence_end_char=snippet.start_char + closest.end,
        )
        marked[place] = replace(found[place], snippet=snippet)
    return marked


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
        The page's assets with their scores and snippets. Empty, with `has_more` false, when
        nothing matches or the page is past the end.

    Raises:
        Exception: A database or vendor error, raised as it comes.
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

    # Load rows and snippets.
    found = fetch_found_assets(page_matches)

    # Rerank within the page.
    descriptions = [found_asset.asset["description"] for found_asset in found]
    new_order = get_reranker().rerank(query, descriptions)
    results = [found[index] for index in new_order]

    # Point the passages matched by meaning at their closest sentence. The query vector is
    # already cached, so this asks the embedder only for the sentences.
    results = mark_closest_sentences(embed_query(model, query), results)
    sentence_count = 0
    for result in results:
        if result.snippet.sentence_start_char is not None:
            sentence_count += 1

    logger.info(
        "search_done collection=%s units_keyword=%s units_vector=%s assets=%s sentences=%s ms=%s",
        collection,
        len(keyword_hits),
        len(vector_hits),
        len(matches),
        sentence_count,
        round((time.perf_counter() - started) * 1000, 1),
    )
    return ResultPage(results=results, has_more=has_more)
