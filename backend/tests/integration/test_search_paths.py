"""The keyword and vector paths, over units written straight into the database, so every
ordering is known in advance."""

import uuid

from sqlalchemy import insert, text

from kms.config import get_settings
from kms.models import EMBEDDING_DIMS, assets, search_units
from kms.search import UnitHit
from kms.search.keyword import keyword_search
from kms.search.vector import vector_search

MODEL = "fake-embedder"


def insert_asset(db, collection):
    row = {
        "collection": collection,
        "filename": "file.txt",
        "asset_type": "text",
        "mime": "text/plain",
        "size_bytes": 1,
        "sha256": uuid.uuid4().hex,
        "status": "ready",
    }
    with db.begin() as connection:
        return connection.execute(insert(assets).values(row).returning(assets.c.id)).scalar_one()


def insert_unit(db, asset_id, collection, body=None, embedding=None, embedding_model=MODEL):
    row = {
        "asset_id": asset_id,
        "collection": collection,
        "kind": "content",
        "body": body,
        "embedding": embedding,
        "embedding_model": embedding_model,
    }
    with db.begin() as connection:
        return connection.execute(
            insert(search_units).values(row).returning(search_units.c.id)
        ).scalar_one()


def axis_vector(*axes):
    """A vector pointing along the given axes; the closer two axis sets, the closer the vectors."""
    vector = [0.0] * EMBEDDING_DIMS
    for axis in axes:
        vector[axis] = 1.0
    return vector


def unit_ids(hits):
    return [hit.unit_id for hit in hits]


# --- keyword path ------------------------------------------------------------


def test_keyword_ranks_the_best_matching_unit_first(db):
    asset_id = insert_asset(db, "demo")
    once = insert_unit(db, asset_id, "demo", "a walk along the harbour at dusk")
    thrice = insert_unit(db, asset_id, "demo", "harbour boats, harbour lights, harbour wall")
    insert_unit(db, asset_id, "demo", "a note about the mountains")

    hits = keyword_search("demo", "harbour", limit=10)

    assert hits == [
        UnitHit(
            unit_id=thrice,
            asset_id=asset_id,
            rank=1,
            all_words=True,
            unit_kind="content",
            asset_type="text",
        ),
        UnitHit(
            unit_id=once,
            asset_id=asset_id,
            rank=2,
            all_words=True,
            unit_kind="content",
            asset_type="text",
        ),
    ]


def test_keyword_matches_word_forms(db):
    asset_id = insert_asset(db, "demo")
    unit_id = insert_unit(db, asset_id, "demo", "the boat left early")

    assert unit_ids(keyword_search("demo", "boats", limit=10)) == [unit_id]


def test_keyword_stays_inside_the_collection(db):
    inside = insert_unit(db, insert_asset(db, "demo"), "demo", "black hair")
    insert_unit(db, insert_asset(db, "other"), "other", "black hair")

    assert unit_ids(keyword_search("demo", "black hair", limit=10)) == [inside]


def test_keyword_query_of_stop_words_returns_nothing(db):
    insert_unit(db, insert_asset(db, "demo"), "demo", "the and of")

    assert keyword_search("demo", "the and of", limit=10) == []


def test_keyword_understands_quotes_and_minus(db):
    asset_id = insert_asset(db, "demo")
    phrase = insert_unit(db, asset_id, "demo", "black hair tied back")
    apart = insert_unit(db, asset_id, "demo", "hair that is black")

    assert unit_ids(keyword_search("demo", '"black hair"', limit=10)) == [phrase]
    assert unit_ids(keyword_search("demo", "hair -tied", limit=10)) == [apart]


def test_keyword_plain_query_finds_units_with_some_words(db):
    asset_id = insert_asset(db, "demo")
    bridge = insert_unit(db, asset_id, "demo", "london bridge")
    insert_unit(db, asset_id, "demo", "paris metro")

    hits = keyword_search("demo", "london meuseum", limit=10)

    assert unit_ids(hits) == [bridge]
    assert hits[0].all_words is False


def test_keyword_all_words_rank_before_some_words(db):
    asset_id = insert_asset(db, "demo")
    # The partial unit repeats its word, so it would rank first on ts_rank alone.
    partial = insert_unit(db, asset_id, "demo", "london london london london")
    exact = insert_unit(db, asset_id, "demo", "a museum in london")

    hits = keyword_search("demo", "london museum", limit=10)

    assert unit_ids(hits) == [exact, partial]
    assert [hit.all_words for hit in hits] == [True, False]


def test_hits_carry_unit_kind_and_asset_type(db):
    asset_id = insert_asset(db, "demo")
    insert_unit(db, asset_id, "demo", "harbour", embedding=axis_vector(0))

    keyword_hit = keyword_search("demo", "harbour", limit=10)[0]
    vector_hit = vector_search("demo", axis_vector(0), MODEL, limit=10)[0]

    for hit in (keyword_hit, vector_hit):
        assert (hit.unit_kind, hit.asset_type) == ("content", "text")
    assert vector_hit.all_words is False


def test_keyword_odd_input_does_not_raise(db):
    unit_id = insert_unit(db, insert_asset(db, "demo"), "demo", "the harbour")

    assert unit_ids(keyword_search("demo", 'harbour & | ! ( " :*', limit=10)) == [unit_id]


def test_keyword_ties_break_on_unit_id(db):
    asset_id = insert_asset(db, "demo")
    first = insert_unit(db, asset_id, "demo", "harbour lights")
    second = insert_unit(db, asset_id, "demo", "harbour lights")
    third = insert_unit(db, asset_id, "demo", "harbour lights")

    for _ in range(3):
        assert unit_ids(keyword_search("demo", "harbour", limit=10)) == [first, second, third]


def test_keyword_returns_at_most_limit(db):
    asset_id = insert_asset(db, "demo")
    for _ in range(3):
        insert_unit(db, asset_id, "demo", "harbour")

    hits = keyword_search("demo", "harbour", limit=2)

    assert [hit.rank for hit in hits] == [1, 2]


# --- vector path -------------------------------------------------------------


def test_vector_ranks_the_nearest_unit_first(db):
    asset_id = insert_asset(db, "demo")
    far = insert_unit(db, asset_id, "demo", embedding=axis_vector(1))
    near = insert_unit(db, asset_id, "demo", embedding=axis_vector(0))
    between = insert_unit(db, asset_id, "demo", embedding=axis_vector(0, 1))

    hits = vector_search("demo", axis_vector(0), MODEL, limit=10)

    assert hits == [
        UnitHit(
            unit_id=near,
            asset_id=asset_id,
            rank=1,
            all_words=False,
            unit_kind="content",
            asset_type="text",
        ),
        UnitHit(
            unit_id=between,
            asset_id=asset_id,
            rank=2,
            all_words=False,
            unit_kind="content",
            asset_type="text",
        ),
        UnitHit(
            unit_id=far,
            asset_id=asset_id,
            rank=3,
            all_words=False,
            unit_kind="content",
            asset_type="text",
        ),
    ]


def test_vector_stays_inside_the_collection(db):
    inside = insert_unit(db, insert_asset(db, "demo"), "demo", embedding=axis_vector(1))
    insert_unit(db, insert_asset(db, "other"), "other", embedding=axis_vector(0))

    assert unit_ids(vector_search("demo", axis_vector(0), MODEL, limit=10)) == [inside]


def test_vector_skips_units_of_another_embedding_model(db):
    asset_id = insert_asset(db, "demo")
    same_model = insert_unit(db, asset_id, "demo", embedding=axis_vector(1))
    insert_unit(db, asset_id, "demo", embedding=axis_vector(0), embedding_model="other-model")

    assert unit_ids(vector_search("demo", axis_vector(0), MODEL, limit=10)) == [same_model]


def test_vector_ties_break_on_unit_id(db):
    asset_id = insert_asset(db, "demo")
    first = insert_unit(db, asset_id, "demo", embedding=axis_vector(0))
    second = insert_unit(db, asset_id, "demo", embedding=axis_vector(0))
    third = insert_unit(db, asset_id, "demo", embedding=axis_vector(0))

    for _ in range(3):
        hits = vector_search("demo", axis_vector(0), MODEL, limit=10)
        assert unit_ids(hits) == [first, second, third]


def test_vector_returns_at_most_limit(db):
    asset_id = insert_asset(db, "demo")
    for axis in range(3):
        insert_unit(db, asset_id, "demo", embedding=axis_vector(axis))

    hits = vector_search("demo", axis_vector(0), MODEL, limit=2)

    assert [hit.rank for hit in hits] == [1, 2]


def test_vector_index_settings_last_only_for_the_transaction(db):
    insert_unit(db, insert_asset(db, "demo"), "demo", embedding=axis_vector(0))

    vector_search("demo", axis_vector(0), MODEL, limit=10)

    # With one idle connection in the pool, this is the one the search just used. The second
    # argument, true, gives null instead of an error if the setting was never loaded.
    with db.connect() as connection:
        ef_search = connection.execute(
            text("SELECT current_setting('hnsw.ef_search', true)")
        ).scalar()
        iterative_scan = connection.execute(
            text("SELECT current_setting('hnsw.iterative_scan', true)")
        ).scalar()
    assert ef_search != str(get_settings().hnsw_ef_search)
    assert iterative_scan != "relaxed_order"
