from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from kms.api.schemas import (
    COLLECTION_NAME_PATTERN,
    Asset,
    SearchResponse,
    SearchResult,
    Snippet,
)
from kms.config import get_settings
from kms.search.service import search

router = APIRouter()


@router.get("/api/search")
def search_collection(
    collection: Annotated[str, Query(pattern=COLLECTION_NAME_PATTERN)],
    q: str,
    page: Annotated[int, Query(ge=1)] = 1,
) -> SearchResponse:
    """One page of the assets in a collection that match a query, best first.

    Args:
        collection: The collection to search in.
        q: The query as typed.
        page: The page to return, from 1.

    Returns:
        The page's results with their scores and snippets. Empty for an unknown collection,
        for no match and for a page past the end.

    Raises:
        HTTPException: 422 if the query is empty or only spaces.
    """
    # A query of only spaces passes FastAPI's own checks, so it is caught here.
    if not q.strip():
        raise HTTPException(status_code=422, detail="q: must not be blank.")

    result_page = search(collection, q, page)

    results = []
    for found in result_page.results:
        snippet = Snippet(
            kind=found.snippet.kind,
            text=found.snippet.text,
            start_char=found.snippet.start_char,
            end_char=found.snippet.end_char,
        )
        results.append(
            SearchResult(asset=Asset.from_row(found.asset), score=found.score, snippet=snippet)
        )
    return SearchResponse(
        results=results,
        page=page,
        page_size=get_settings().page_size,
        has_more=result_page.has_more,
    )
