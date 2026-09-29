"""GET /api/search end to end: units written straight into the database behind a stub embedder,
so every ordering is known in advance, and files taken through upload and the worker with the
fake adapters."""

import io
import uuid
from typing import Literal

import pytest
from PIL import Image
from sqlalchemy import insert, update

from kms.ai import set_embedder
from kms.ai.errors import RetryPolicy
from kms.ai.interfaces import Embedder, Reranker
from kms.config import get_settings
from kms.ingest.worker import run_once
from kms.models import EMBEDDING_DIMS, assets, search_units
from kms.search import service
from kms.search.service import embed_query, relevance_cache

STUB_MODEL = "stub-embedder"


def axis_vector(*axes):
    """A vector pointing along the given axes; the closer two axis sets, the closer the vectors."""
    vector = [0.0] * EMBEDDING_DIMS
    for axis in axes:
        vector[axis] = 1.0
    return vector


class StubEmbedder(Embedder):
    """Embeds every input as `vector`, which a test may change; along axis 0 unless it does. A
    text in `vectors_by_text` gets its own vector instead."""

    model = STUB_MODEL

    def __init__(self):
        self.vector = axis_vector(0)
        self.vectors_by_text: dict[str, list[float]] = {}

    def embed(
        self,
        inputs: list[str | bytes],
        input_type: Literal["document", "query"],
        policy: RetryPolicy,
    ) -> list[list[float]]:
        return [self.vectors_by_text.get(item, self.vector) for item in inputs]


@pytest.fixture
def stub_embedder():
    # The query cache outlives a test, so it is emptied on the way in and on the way out.
    embedder = StubEmbedder()
    set_embedder(embedder)
    embed_query.cache_clear()
    yield embedder
    set_embedder(None)
    embed_query.cache_clear()


class StubReranker(Reranker):
    """Scores each text with the relevance a test gave it, 0.5 when it gave none."""

    def __init__(self, relevance_by_text: dict[str, float] | None = None):
        self.relevance_by_text = relevance_by_text or {}

    def rerank(self, query: str, documents: list[str], policy: RetryPolicy) -> list[float]:
        return [self.relevance_by_text.get(text, 0.5) for text in documents]


@pytest.fixture
def use_reranker(monkeypatch):
    # Puts in the reranker a test builds. The cache outlives a test, so it is emptied on the way
    # in and on the way out.
    relevance_cache.clear()
    yield lambda reranker: monkeypatch.setattr(service, "get_reranker", lambda: reranker)
    relevance_cache.clear()


def insert_asset(db, collection, filename="file.txt", asset_type="text"):
    row = {
        "collection": collection,
        "filename": filename,
        "asset_type": asset_type,
        "mime": "text/plain",
        "size_bytes": 1,
        "sha256": uuid.uuid4().hex,
        "status": "ready",
        "title": filename,
        "description": "A text file.",
        "tags": [],
    }
    with db.begin() as connection:
        return connection.execute(insert(assets).values(row).returning(assets.c.id)).scalar_one()


def insert_unit(
    db,
    asset_id,
    collection,
    body=None,
    embedding=None,
    start_char=None,
    end_char=None,
    kind="content",
):
    # A unit without a vector gets no model either, so the vector path never sees it.
    embedding_model = None
    if embedding is not None:
        embedding_model = STUB_MODEL
    row = {
        "asset_id": asset_id,
        "collection": collection,
        "kind": kind,
        "start_char": start_char,
        "end_char": end_char,
        "body": body,
        "embedding": embedding,
        "embedding_model": embedding_model,
    }
    with db.begin() as connection:
        return connection.execute(
            insert(search_units).values(row).returning(search_units.c.id)
        ).scalar_one()


def jpeg_bytes(colour: str) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), colour).save(buffer, format="JPEG")
    return buffer.getvalue()


def post_file(client, filename: str, data: bytes, collection: str = "demo"):
    return client.post(
        "/api/assets",
        files={"file": (filename, data, "application/octet-stream")},
        data={"collection": collection},
    )


def search(client, query, collection="demo", page=1, **options):
    params = {"collection": collection, "q": query, "page": page, **options}
    response = client.get("/api/search", params=params)
    assert response.status_code == 200
    return response.json()


def result_ids(body):
    return [result["asset"]["id"] for result in body["results"]]


def result_filenames(body):
    return [result["asset"]["filename"] for result in body["results"]]


# --- parameters --------------------------------------------------------------


def test_rejects_invalid_parameters(client):
    invalid_params = [
        {"collection": "Bad Name", "q": "harbour"},
        {"collection": "demo"},
        {"collection": "demo", "q": ""},
        {"collection": "demo", "q": "   "},
        {"collection": "demo", "q": "harbour", "page": 0},
        {"collection": "demo", "q": "harbour", "order": "newest"},
        {"collection": "demo", "q": "harbour", "match": "close"},
        {"collection": "demo", "q": "harbour", "asset_type": "video"},
        {"collection": "demo", "q": "harbour", "found_in": "title"},
    ]
    for params in invalid_params:
        response = client.get("/api/search", params=params)
        assert response.status_code == 422, params
        assert isinstance(response.json()["detail"], str), params


def test_unknown_collection_gives_no_results(client, stub_embedder):
    body = search(client, "harbour", collection="nothing-here")

    assert body == {
        "results": [],
        "page": 1,
        "page_size": get_settings().page_size,
        "has_more": False,
    }


# --- what is searchable ------------------------------------------------------


def test_pending_asset_is_absent_until_ready(client):
    post_file(client, "walk.txt", b"A walk along the harbour at dusk.\n")

    assert search(client, "harbour")["results"] == []

    assert run_once() is True

    assert result_filenames(search(client, "harbour")) == ["walk.txt"]


# --- ranking and results -----------------------------------------------------


def test_asset_on_both_paths_outranks_assets_on_one_path(client, db, stub_embedder):
    keyword_only = insert_asset(db, "demo")
    insert_unit(db, keyword_only, "demo", body="harbour")
    vector_only = insert_asset(db, "demo")
    # A content unit always has its offsets, as the worker writes it.
    insert_unit(
        db, vector_only, "demo", body="mountain", embedding=axis_vector(0), start_char=0, end_char=8
    )
    # Inserted last, so it loses every tie on unit id and wins only by being on both paths.
    both_paths = insert_asset(db, "demo")
    insert_unit(db, both_paths, "demo", body="harbour", embedding=axis_vector(0))

    body = search(client, "harbour")

    assert result_ids(body)[0] == str(both_paths)
    assert set(result_ids(body)) == {str(keyword_only), str(vector_only), str(both_paths)}


def test_top_result_scores_one(client, db, stub_embedder):
    near = insert_asset(db, "demo")
    insert_unit(db, near, "demo", body="harbour", embedding=axis_vector(0))
    far = insert_asset(db, "demo")
    # A content unit always has its offsets, as the worker writes it.
    insert_unit(
        db, far, "demo", body="mountain", embedding=axis_vector(1), start_char=0, end_char=8
    )

    scores = [result["score"] for result in search(client, "harbour")["results"]]

    assert scores[0] == 1.0
    assert all(score < 1.0 for score in scores[1:])
    assert len(scores) == 2


def test_search_stays_inside_the_collection(client, db, stub_embedder):
    inside = insert_asset(db, "demo")
    insert_unit(db, inside, "demo", body="harbour", embedding=axis_vector(0))
    outside = insert_asset(db, "other")
    insert_unit(db, outside, "other", body="harbour", embedding=axis_vector(0))

    assert result_ids(search(client, "harbour")) == [str(inside)]


def test_text_hit_points_at_the_chunk_offsets(client, db, stub_embedder):
    asset_id = insert_asset(db, "demo")
    insert_unit(
        db,
        asset_id,
        "demo",
        body="the harbour at dusk",
        embedding=axis_vector(0),
        start_char=120,
        end_char=139,
    )

    snippet = search(client, "harbour")["results"][0]["snippet"]

    assert snippet == {
        "kind": "content",
        "text": "the harbour at dusk",
        "start_char": 120,
        "end_char": 139,
        "sentence_start": None,
        "sentence_end": None,
    }


# --- paging ------------------------------------------------------------------


def test_page_two_continues_without_repeats(client, db, stub_embedder):
    page_size = get_settings().page_size
    for _ in range(page_size + 5):
        asset_id = insert_asset(db, "demo")
        insert_unit(db, asset_id, "demo", body="harbour", embedding=axis_vector(0))

    first_page = search(client, "harbour", page=1)
    second_page = search(client, "harbour", page=2)

    assert len(first_page["results"]) == page_size
    assert first_page["has_more"] is True
    assert len(second_page["results"]) == 5
    assert second_page["has_more"] is False
    assert second_page["page"] == 2
    assert set(result_ids(first_page)).isdisjoint(result_ids(second_page))


def test_results_stop_at_the_cap(client, db, stub_embedder):
    max_assets = get_settings().max_assets_per_query
    # Every asset matches the keyword; only the last one, inserted last and so the one the
    # keyword path leaves out when it is full, is also near the query. The two paths together
    # find one asset more than the cap.
    for _ in range(max_assets):
        asset_id = insert_asset(db, "demo")
        insert_unit(db, asset_id, "demo", body="harbour", embedding=axis_vector(1))
    last_asset = insert_asset(db, "demo")
    insert_unit(db, last_asset, "demo", body="harbour", embedding=axis_vector(0))

    found_ids = []
    page = 1
    while True:
        body = search(client, "harbour", page=page)
        found_ids.extend(result_ids(body))
        if not body["has_more"]:
            break
        page += 1

    assert len(found_ids) == max_assets
    assert len(set(found_ids)) == max_assets
    assert search(client, "harbour", page=page + 1)["results"] == []


# --- kinds of file and filenames ---------------------------------------------


def test_picture_ranks_images_first_and_document_ranks_text_files_first(client):
    post_file(client, "IMG_2101.jpg", jpeg_bytes("red"))
    post_file(client, "IMG_2114.jpg", jpeg_bytes("blue"))
    post_file(client, "walk.txt", b"A walk along the harbour at dusk.\n")
    post_file(client, "train.txt", b"The train to Porto leaves at nine.\n")
    for _ in range(4):
        assert run_once() is True

    picture_top = result_filenames(search(client, "picture"))[:2]
    document_top = result_filenames(search(client, "document"))[:2]

    assert set(picture_top) == {"IMG_2101.jpg", "IMG_2114.jpg"}
    assert set(document_top) == {"walk.txt", "train.txt"}


def test_filename_word_finds_the_asset(client):
    post_file(client, "IMG_2101.jpg", jpeg_bytes("red"))
    post_file(client, "IMG_2114.jpg", jpeg_bytes("blue"))
    for _ in range(2):
        assert run_once() is True

    top_result = search(client, "2101")["results"][0]

    assert top_result["asset"]["filename"] == "IMG_2101.jpg"
    assert top_result["snippet"] == {
        "kind": "filename",
        "text": "IMG_2101.jpg",
        "start_char": None,
        "end_char": None,
        "sentence_start": None,
        "sentence_end": None,
    }


# --- match kinds, order and filters ------------------------------------------


def insert_three_kinds(db):
    """Three assets that match "london museum" exactly, partly, and by meaning only. The
    semantic one is nearest the query vector and so scores best on its own."""
    exact = insert_asset(db, "demo", "exact.txt")
    insert_unit(db, exact, "demo", body="a museum in london")
    partial = insert_asset(db, "demo", "partial.txt")
    insert_unit(db, partial, "demo", body="london bridge")
    semantic = insert_asset(db, "demo", "semantic.jpg", asset_type="image")
    insert_unit(db, semantic, "demo", body="soup cans", embedding=axis_vector(0), kind="image")
    return str(exact), str(partial), str(semantic)


def test_result_carries_its_match_kind(client, db, stub_embedder):
    exact, partial, semantic = insert_three_kinds(db)

    body = search(client, "london museum")

    matches = {result["asset"]["id"]: result["match"] for result in body["results"]}
    assert matches == {exact: "exact", partial: "partial", semantic: "semantic"}


def test_each_order(client, db, stub_embedder):
    exact, partial, semantic = insert_three_kinds(db)

    exact_first = result_ids(search(client, "london museum", order="exact_first"))
    tiered = result_ids(search(client, "london museum", order="tiered"))
    blended = result_ids(search(client, "london museum", order="blended"))

    assert exact_first[0] == exact
    assert tiered == [exact, partial, semantic]
    # Each asset is on one path at rank 1 or 2, so fusion alone puts partial last.
    assert blended == [exact, semantic, partial]


def test_match_filter_keeps_chosen_kinds_with_unchanged_scores(client, db, stub_embedder):
    exact, partial, semantic = insert_three_kinds(db)
    scores = {
        result["asset"]["id"]: result["score"]
        for result in search(client, "london museum")["results"]
    }

    body = search(client, "london museum", match=["partial", "semantic"])

    assert set(result_ids(body)) == {partial, semantic}
    for result in body["results"]:
        assert result["score"] == scores[result["asset"]["id"]]


def test_asset_type_and_found_in_filters(client, db, stub_embedder):
    exact, partial, semantic = insert_three_kinds(db)

    assert result_ids(search(client, "london museum", asset_type="image")) == [semantic]
    assert set(result_ids(search(client, "london museum", asset_type="text"))) == {exact, partial}
    assert result_ids(search(client, "london museum", found_in="image")) == [semantic]
    assert search(client, "london museum", found_in="filename")["results"] == []


def test_found_in_takes_the_snippet_from_the_chosen_part(client, db, stub_embedder):
    asset_id = insert_asset(db, "demo", "lisbon.txt")
    insert_unit(db, asset_id, "demo", body="lisbon", kind="metadata")
    insert_unit(db, asset_id, "demo", body="a day in lisbon", start_char=0, end_char=15)

    unfiltered = search(client, "lisbon")["results"][0]["snippet"]["kind"]
    content_only = search(client, "lisbon", found_in="content")["results"][0]["snippet"]["kind"]

    assert unfiltered == "metadata"
    assert content_only == "content"


def insert_form_image(db):
    """An image whose description does not hold "israeli" but whose text in the image does."""
    asset_id = insert_asset(db, "demo", "IMG_2168.jpg", asset_type="image")
    with db.begin() as connection:
        connection.execute(
            update(assets).where(assets.c.id == asset_id).values(visible_text="Nationality Israeli")
        )
    insert_unit(db, asset_id, "demo", body="A hotel registration form.", kind="metadata")
    insert_unit(db, asset_id, "demo", body="Nationality Israeli", kind="visible_text")
    return asset_id


def test_word_only_in_image_text_is_found_in_visible_text(client, db, stub_embedder):
    asset_id = insert_form_image(db)

    result = search(client, "israeli")["results"][0]

    assert result["asset"]["id"] == str(asset_id)
    assert result["match"] == "exact"
    assert result["snippet"]["kind"] == "visible_text"
    assert result["snippet"]["text"] == "Nationality Israeli"


def test_found_in_without_visible_text_drops_image_text_match(client, db, stub_embedder):
    insert_form_image(db)

    body = search(client, "israeli", found_in=["metadata", "content", "image", "filename"])

    assert body["results"] == []


# --- closest sentence ----------------------------------------------------------


def test_semantic_text_hit_points_at_closest_sentence(client, db, stub_embedder):
    # No word of "pastry" is in the passage, so only the vector path finds it; its second
    # sentence points the way the query does.
    passage = "The tram climbs the hill. A small bakery sells custard tarts."
    asset_id = insert_asset(db, "demo", "lisbon.txt")
    insert_unit(
        db,
        asset_id,
        "demo",
        body=passage,
        embedding=axis_vector(0),
        start_char=500,
        end_char=500 + len(passage),
    )
    stub_embedder.vectors_by_text = {"The tram climbs the hill.": axis_vector(1)}

    result = search(client, "pastry")["results"][0]

    assert result["match"] == "semantic"
    # The second sentence starts 26 characters into the passage, counted in the snippet's text.
    assert result["snippet"]["sentence_start"] == 26
    assert result["snippet"]["sentence_end"] == len(passage)


def test_exact_hit_has_no_sentence(client, db, stub_embedder):
    asset_id = insert_asset(db, "demo", "lisbon.txt")
    insert_unit(
        db,
        asset_id,
        "demo",
        body="The tram climbs the hill. A small bakery sells custard tarts.",
        embedding=axis_vector(0),
        start_char=0,
        end_char=61,
    )

    result = search(client, "custard tarts")["results"][0]

    assert result["match"] == "exact"
    assert result["snippet"]["sentence_start"] is None
    assert result["snippet"]["sentence_end"] is None


# --- relevance ---------------------------------------------------------------


def test_default_order_is_relevance(client, db, stub_embedder, use_reranker):
    exact, partial, semantic = insert_three_kinds(db)
    # The image's snippet is its description.
    relevance_by_text = {"london bridge": 0.9, "a museum in london": 0.4, "A text file.": 0.1}
    use_reranker(StubReranker(relevance_by_text))

    body = search(client, "london museum")

    assert result_ids(body) == [partial, exact, semantic]
    assert [result["relevance"] for result in body["results"]] == [0.9, 0.4, 0.1]


def test_page_two_has_no_relevance(client, db, stub_embedder, use_reranker):
    use_reranker(StubReranker())
    page_size = get_settings().page_size
    for _ in range(page_size + 5):
        asset_id = insert_asset(db, "demo")
        insert_unit(db, asset_id, "demo", body="harbour", embedding=axis_vector(0))

    first_page = search(client, "harbour", page=1)
    second_page = search(client, "harbour", page=2)

    assert all(result["relevance"] == 0.5 for result in first_page["results"])
    assert all(result["relevance"] is None for result in second_page["results"])


def test_results_past_the_candidates_have_no_relevance(
    client, db, stub_embedder, use_reranker, monkeypatch
):
    monkeypatch.setenv("RERANK_CANDIDATES", "2")
    get_settings.cache_clear()
    use_reranker(StubReranker())
    for _ in range(4):
        asset_id = insert_asset(db, "demo")
        insert_unit(db, asset_id, "demo", body="harbour", embedding=axis_vector(0))

    body = search(client, "harbour")
    get_settings.cache_clear()

    assert [result["relevance"] for result in body["results"]] == [0.5, 0.5, None, None]
