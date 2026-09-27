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
from kms.search.service import search

router = APIRouter()


@router.get("/api/search")
def search_collection(
    collection: Annotated[str, Query(pattern=COLLECTION_NAME_PATTERN)],
    q: str,
    page: Annotated[int, Query(ge=1)] = 1,
    order: SearchOrder = SearchOrder.EXACT_FIRST,
    match: Annotated[list[MatchKind] | None, Query()] = None,
    asset_type: Annotated[list[Literal["image", "text"]] | None, Query()] = None,
    found_in: Annotated[
        list[Literal["metadata", "content", "image", "filename"]] | None, Query()
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
        The page's results with their scores and snippets. Empty for an unknown collection,
        for no match and for a page past the end.

    Raises:
        HTTPException: 422 if the query is empty or only spaces.
    """
    # A query of only spaces passes FastAPI's own checks, so it is caught here.
    if not q.strip():
        raise HTTPException(status_code=422, detail="q: must not be blank.")

    result_page = search(collection, q, page, order, match, asset_type, found_in)

    results = []
    for found in result_page.results:
        snippet = Snippet(
            kind=found.snippet.kind,
            text=found.snippet.text,
            start_char=found.snippet.start_char,
            end_char=found.snippet.end_char,
        )
        results.append(
            SearchResult(
                asset=Asset.from_row(found.asset),
                score=found.score,
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
