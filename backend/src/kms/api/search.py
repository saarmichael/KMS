from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from kms.api.schemas import (
    COLLECTION_NAME_PATTERN,
    Asset,
    SearchResponse,
    SearchResult,
    Snippet,
)
from kms.config import get_settings
from kms.search import MatchKind
from kms.search.order import SearchOrder
from kms.search.service import QueryEmbeddingFailed, search

router = APIRouter()

# Long enough for any question a person types; a longer query only makes a larger SQL statement.
MAX_QUERY_CHARS = 500


@router.get("/api/search")
def search_collection(
    collection: Annotated[str, Query(pattern=COLLECTION_NAME_PATTERN)],
    q: Annotated[str, Query(max_length=MAX_QUERY_CHARS)],
    page: Annotated[int, Query(ge=1)] = 1,
    order: SearchOrder = SearchOrder.RELEVANCE,
    match: Annotated[list[MatchKind] | None, Query()] = None,
    asset_type: Annotated[list[Literal["image", "text"]] | None, Query()] = None,
    found_in: Annotated[
        list[Literal["metadata", "content", "image", "visible_text", "filename"]] | None, Query()
    ] = None,
) -> SearchResponse:
    """One page of the assets in a collection that match a query, in the chosen order.

    The three filters are repeatable parameters (`match=exact&match=partial`); a filter left out
    keeps everything. FastAPI answers a value outside the allowed ones with 422.

    Args:
        collection: The collection to search in.
        q: The query as typed.
        page: The page to return, from 1.
        order: How to order the results.
        match: Keep only results that matched this way.
        asset_type: Keep only results of these asset types.
        found_in: Keep only results that matched in these parts of an asset.

    Returns:
        The page's results with their scores, relevances and snippets. Empty for an unknown
        collection, for no match and for a page past the end.

    Raises:
        HTTPException: 422 if the query is empty, only spaces or too long; 503 if the embedding
            service did not answer for the query.
    """
    # A query of only spaces passes FastAPI's own checks, so it is caught here.
    if not q.strip():
        raise HTTPException(status_code=422, detail="q: must not be blank.")

    try:
        result_page = search(collection, q, page, order, match, asset_type, found_in)
    except QueryEmbeddingFailed:
        # An outage on the vendor's side, not a bug on ours, and it may pass in a moment.
        raise HTTPException(
            status_code=503,
            detail="Search is unavailable: the embedding service did not answer. "
            "Try again in a moment.",
        ) from None

    results = []
    for found in result_page.results:
        snippet = Snippet(
            kind=found.snippet.kind,
            text=found.snippet.text,
            start_char=found.snippet.start_char,
            end_char=found.snippet.end_char,
            sentence_start=found.snippet.sentence_start,
            sentence_end=found.snippet.sentence_end,
        )
        results.append(
            SearchResult(
                asset=Asset.from_row(found.asset),
                score=found.score,
                relevance=found.relevance,
                snippet=snippet,
                match=found.match,
            )
        )
    return SearchResponse(
        results=results,
        page=page,
        page_size=get_settings().page_size,
        has_more=result_page.has_more,
    )
