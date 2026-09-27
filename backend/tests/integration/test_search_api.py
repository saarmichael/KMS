"""GET /api/search end to end: units written straight into the database behind a stub embedder,
so every ordering is known in advance, and files taken through upload and the worker with the
fake adapters."""

import io
import uuid
from typing import Literal

import pytest
from PIL import Image
from sqlalchemy import insert

from kms.ai import set_embedder
from kms.ai.interfaces import Embedder
from kms.config import get_settings
from kms.ingest.worker import run_once
from kms.models import EMBEDDING_DIMS, assets, search_units
from kms.search.service import embed_query

STUB_MODEL = "stub-embedder"


def axis_vector(*axes):
    """A vector pointing along the given axes; the closer two axis sets, the closer the vectors."""
    vector = [0.0] * EMBEDDING_DIMS
    for axis in axes:
        vector[axis] = 1.0
    return vector


class StubEmbedder(Embedder):
    """Embeds every query as `vector`, which a test may change; along axis 0 unless it does."""

    model = STUB_MODEL

    def __init__(self):
        self.vector = axis_vector(0)

    def embed(
        self, inputs: list[str | bytes], input_type: Literal["document", "query"]
    ) -> list[list[float]]:
        return [self.vector for _ in inputs]


@pytest.fixture
def stub_embedder():
    # The query cache outlives a test, so it is emptied on the way in and on the way out.
    embedder = StubEmbedder()
    set_embedder(embedder)
    embed_query.cache_clear()
    yield embedder
    set_embedder(None)
    embed_query.cache_clear()


def insert_asset(db, collection, filename="file.txt"):
    row = {
        "collection": collection,
        "filename": filename,
        "asset_type": "text",
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
    db, asset_id, collection, body=None, embedding=None, start_char=None, end_char=None
):
    # A unit without a vector gets no model either, so the vector path never sees it.
    embedding_model = None
    if embedding is not None:
        embedding_model = STUB_MODEL
    row = {
        "asset_id": asset_id,
        "collection": collection,
        "kind": "content",
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


def search(client, query, collection="demo", page=1):
    response = client.get(
        "/api/search", params={"collection": collection, "q": query, "page": page}
    )
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
    insert_unit(db, vector_only, "demo", body="mountain", embedding=axis_vector(0))
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
    insert_unit(db, far, "demo", body="mountain", embedding=axis_vector(1))

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
    }
