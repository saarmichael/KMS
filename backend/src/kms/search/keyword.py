"""The keyword path: full-text search over the units' text."""

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import websearch_to_tsquery

from kms.db import get_engine
from kms.models import search_units
from kms.search import UnitHit


def keyword_search(collection: str, query: str, limit: int) -> list[UnitHit]:
    """Find the units of a collection whose text matches the query, best first.

    Args:
        collection: The collection to search in.
        query: The query as typed. Quoted phrases, `-word` and `or` are understood; every other
            word must appear in the unit.
        limit: The most units to return.

    Returns:
        At most `limit` hits, ranked from 1. Empty when nothing matches, when the query holds
        only stop words, or when the collection is unknown.
    """
    # The same configuration that builds `tsv`, so query words are stemmed the same way.
    # websearch_to_tsquery never raises on what a user types, unlike to_tsquery.
    tsquery = websearch_to_tsquery("english", query)
    matches = (
        select(search_units.c.id, search_units.c.asset_id)
        .where(search_units.c.collection == collection)
        .where(search_units.c.tsv.bool_op("@@")(tsquery))
        # The unit id breaks ties, so the same query always gives the same order.
        .order_by(func.ts_rank(search_units.c.tsv, tsquery).desc(), search_units.c.id)
        .limit(limit)
    )
    with get_engine().connect() as connection:
        rows = connection.execute(matches).all()

    hits = []
    for rank, row in enumerate(rows, start=1):
        hits.append(UnitHit(unit_id=row.id, asset_id=row.asset_id, rank=rank))
    return hits
