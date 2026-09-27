"""The vector path: nearest units to the query vector, by cosine distance."""

from sqlalchemy import func, select

from kms.config import get_settings
from kms.db import get_engine
from kms.models import search_units
from kms.search import UnitHit


def vector_search(
    collection: str, query_vector: list[float], embedding_model: str, limit: int
) -> list[UnitHit]:
    """Find the units of a collection nearest to the query vector, best first.

    Args:
        collection: The collection to search in.
        query_vector: The embedded query.
        embedding_model: The model that made `query_vector`; only units embedded by the same
            model are compared, since vectors of two models are not comparable.
        limit: The most units to return.

    Returns:
        At most `limit` hits, ranked from 1. Empty when the collection has no units of that
        model.
    """
    settings = get_settings()
    distance = search_units.c.embedding.cosine_distance(query_vector).label("distance")
    # Ordered by distance alone, so the HNSW index can serve the scan. MATERIALIZED keeps the
    # planner from merging this ordering with the outer one.
    nearest = (
        select(search_units.c.id, search_units.c.asset_id, distance)
        .where(search_units.c.collection == collection)
        .where(search_units.c.embedding_model == embedding_model)
        .order_by(distance)
        .limit(limit)
        .cte("nearest")
        .prefix_with("MATERIALIZED")
    )
    # relaxed_order may hand rows back slightly out of order, so they are sorted again here;
    # the unit id breaks ties, so the same query always gives the same order.
    ranked = select(nearest.c.id, nearest.c.asset_id).order_by(
        nearest.c.distance, nearest.c.id
    )

    with get_engine().begin() as connection:
        # The last argument, true, makes each setting end with this transaction, so a pooled
        # connection hands nothing over to its next user.
        connection.execute(
            select(func.set_config("hnsw.ef_search", str(settings.hnsw_ef_search), True))
        )
        # Filters apply after the index scan; the iterative scan keeps walking the index until
        # enough rows pass them, instead of stopping at ef_search candidates.
        connection.execute(select(func.set_config("hnsw.iterative_scan", "relaxed_order", True)))
        rows = connection.execute(ranked).all()

    hits = []
    for rank, row in enumerate(rows, start=1):
        hits.append(UnitHit(unit_id=row.id, asset_id=row.asset_id, rank=rank))
    return hits
