"""The keyword path: full-text search over the units' text."""

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import websearch_to_tsquery

from kms.db import get_engine
from kms.models import assets, search_units
from kms.search import UnitHit


def uses_search_syntax(query: str) -> bool:
    """True when the query holds a quote, a word starting with "-", or the word "or". Never
    raises.

    Such a query asks for precise matching, so it keeps the rule that every word must appear.
    """
    if '"' in query:
        return True
    for word in query.lower().split():
        if word == "or" or word.startswith("-"):
            return True
    return False


def any_word_tsquery(query: str):
    """Build a query that matches a unit holding any one of the query's words.

    Each word is parsed on its own and the parts are joined with "or" (`||`). A word that is a
    stop word or punctuation parses to nothing, and Postgres leaves it out of the join.

    Args:
        query: The query as typed; not blank.

    Returns:
        The SQL expression of the combined query.
    """
    words = query.split()
    combined = func.plainto_tsquery("english", words[0])
    for word in words[1:]:
        combined = combined.op("||")(func.plainto_tsquery("english", word))
    return combined


def keyword_search(collection: str, query: str, limit: int) -> list[UnitHit]:
    """Find the units of a collection whose text matches the query, best first.

    Args:
        collection: The collection to search in.
        query: The query as typed. A plain query finds units holding any of its words. A query
            with quotes, `-word` or `or` is understood as such, and every other word must
            appear in the unit.
        limit: The most units to return.

    Returns:
        At most `limit` hits, ranked from 1: units holding every word first, then by how well
        they match. Empty when nothing matches, when the query holds only stop words, or when
        the collection is unknown.
    """
    # The same configuration that builds `tsv`, so query words are stemmed the same way.
    # websearch_to_tsquery never raises on what a user types, unlike to_tsquery.
    all_words_query = websearch_to_tsquery("english", query)
    if uses_search_syntax(query):
        match_query = all_words_query
    else:
        match_query = any_word_tsquery(query)

    all_words = search_units.c.tsv.bool_op("@@")(all_words_query).label("all_words")
    matches = (
        select(
            search_units.c.id,
            search_units.c.asset_id,
            search_units.c.kind,
            assets.c.asset_type,
            all_words,
        )
        .join(assets, assets.c.id == search_units.c.asset_id)
        .where(search_units.c.collection == collection)
        .where(search_units.c.tsv.bool_op("@@")(match_query))
        # The unit id breaks ties, so the same query always gives the same order.
        .order_by(
            all_words.desc(),
            func.ts_rank(search_units.c.tsv, match_query).desc(),
            search_units.c.id,
        )
        .limit(limit)
    )
    with get_engine().connect() as connection:
        rows = connection.execute(matches).all()

    hits = []
    for rank, row in enumerate(rows, start=1):
        hits.append(
            UnitHit(
                unit_id=row.id,
                asset_id=row.asset_id,
                rank=rank,
                all_words=row.all_words,
                unit_kind=row.kind,
                asset_type=row.asset_type,
            )
        )
    return hits
