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


# The BM25 index on `search_units.body`. It does not exist: Railway's Postgres ships no BM25
# extension, so the name only shows what the query would point at.
BM25_INDEX = "ix_search_units_body_bm25"


def keyword_search(collection: str, query: str, limit: int) -> list[UnitHit]:
    """Find the units of a collection whose text matches the query, best first.

    Args:
        collection: The collection to search in.
        query: The query as typed. A plain query finds units holding any of its words. A query
            with quotes, `-word` or `or` is understood as such, and every other word must
            appear in the unit.
        limit: The most units to return.

    Returns:
        The hits of `ts_rank_search`.
    """
    return ts_rank_search(collection, query, limit)


def ts_rank_search(collection: str, query: str, limit: int) -> list[UnitHit]:
    """Find the units of a collection whose text matches the query, ranked by `ts_rank`.

    Args:
        collection: The collection to search in.
        query: The query as typed, as for `keyword_search`.
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
        # ts_rank is computed from each matching row's tsv, so every match is read and scored
        # before the first `limit` can be kept. The unit id breaks ties, so the same query
        # always gives the same order.
        .order_by(
            all_words.desc(),
            func.ts_rank(search_units.c.tsv, match_query).desc(),
            search_units.c.id,
        )
        .limit(limit)
    )
    with get_engine().connect() as connection:
        rows = connection.execute(matches).all()
    return ranked_hits(rows)


def bm25_search(collection: str, query: str, limit: int) -> list[UnitHit]:
    """Find the units of a collection whose text matches the query, ranked by BM25.

    Written as if Postgres had a BM25 index extension (pg_textsearch) and the index
    `BM25_INDEX` on `search_units.body`. Neither exists, so nothing calls this.

    Args:
        collection: The collection to search in.
        query: The query as typed, as for `keyword_search`.
        limit: The most units to return.

    Returns:
        At most `limit` hits, ranked from 1 by BM25 score. Fewer than `limit` when the
        collection or the search syntax rules out some of the units the index ranked best.
    """
    # The index scores every unit holding any of the query's words, so a plain query needs no
    # any-word query of its own. The all-words query is still needed: it labels each hit as
    # holding every word or not, and it carries the phrases and exclusions of search syntax.
    all_words_query = websearch_to_tsquery("english", query)
    all_words = search_units.c.tsv.bool_op("@@")(all_words_query).label("all_words")

    # The operator gives the BM25 score negated, so lower is better and an ascending order is
    # the order the index already holds. Postgres walks the index and stops after `limit`
    # units, reading the table only for those.
    bm25_score = search_units.c.body.op("<@>")(func.to_bm25query(query, BM25_INDEX))

    matches = (
        select(
            search_units.c.id,
            search_units.c.asset_id,
            search_units.c.kind,
            assets.c.asset_type,
            all_words,
        )
        .join(assets, assets.c.id == search_units.c.asset_id)
        # The index holds every collection, so this check runs on the units it returns: a unit
        # of another collection uses up a place, and a small collection can get fewer hits.
        .where(search_units.c.collection == collection)
        # Unlike ts_rank_search, holding every word is not the first sort key. Sorting on it
        # first would make Postgres score and sort every match before keeping any, which is the
        # cost the index is there to avoid; BM25 already ranks units holding more of the rare
        # words higher. The unit id only orders units with equal scores.
        .order_by(bm25_score, search_units.c.id)
        .limit(limit)
    )
    if uses_search_syntax(query):
        # The index knows words, not phrases or exclusions, so those are checked with the
        # all-words query on the units it returns, with the same cost as the collection check.
        matches = matches.where(search_units.c.tsv.bool_op("@@")(all_words_query))

    with get_engine().connect() as connection:
        rows = connection.execute(matches).all()
    return ranked_hits(rows)


def ranked_hits(rows) -> list[UnitHit]:
    """Turn the rows of a keyword query, best first, into hits ranked from 1. Never raises."""
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
