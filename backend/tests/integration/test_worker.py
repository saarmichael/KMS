import io

from PIL import Image
from sqlalchemy import text

from kms.ai import get_embedder
from kms.ai.schema import Metadata, normalise
from kms.config import get_settings
from kms.ingest.chunker import chunk_text
from kms.ingest.upload import upload
from kms.ingest.worker import (
    build_units,
    claim_one,
    commit_ready,
    reaper,
    run_once,
)

NOTE = b"A short note about a woman with black hair.\n"


def jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), "red").save(buffer, format="JPEG")
    return buffer.getvalue()


def load_asset(db, asset_id):
    with db.connect() as connection:
        return (
            connection.execute(text("SELECT * FROM assets WHERE id = :id"), {"id": asset_id})
            .mappings()
            .one()
        )


def load_units(db, asset_id):
    query = text("SELECT * FROM search_units WHERE asset_id = :id ORDER BY kind, unit_index")
    with db.connect() as connection:
        return connection.execute(query, {"id": asset_id}).mappings().all()


def expire_lease(db, asset_id):
    """Move the claim back in time past the lease, instead of waiting for it."""
    minutes = get_settings().lease_minutes + 1
    with db.begin() as connection:
        connection.execute(
            text(
                "UPDATE assets SET started_at = now() - make_interval(mins => :minutes) "
                "WHERE id = :id"
            ),
            {"minutes": minutes, "id": asset_id},
        )


def test_image_becomes_ready_with_metadata_image_and_filename_units(db, blob_store):
    asset_id = upload("demo", "IMG_2101.jpg", jpeg_bytes()).asset["id"]

    assert run_once() is True

    asset = load_asset(db, asset_id)
    assert asset["status"] == "ready"
    assert asset["title"] == "Car key on a red umbrella hook"
    assert asset["image_type"] == "photo"
    assert asset["vision_model"] == "fake-vision"
    assert asset["tags"][-4:] == ["image", "picture", "photo", "photograph"]
    units = load_units(db, asset_id)
    assert [unit["kind"] for unit in units] == ["filename", "image", "metadata"]
    filename_unit, image_unit, metadata_unit = units
    assert filename_unit["body"] == "IMG_2101.jpg IMG 2101 jpg"
    assert filename_unit["start_char"] is None
    assert filename_unit["end_char"] is None
    assert filename_unit["embedding"] is not None
    assert image_unit["body"] is None
    assert image_unit["embedding"] is not None
    assert metadata_unit["body"].startswith("Car key on a red umbrella hook")
    assert {unit["embedding_model"] for unit in units} == {"fake-embedder"}


def test_text_has_one_content_unit_per_chunk(db, blob_store):
    body = " ".join(f"sentence number {number} about the harbour." for number in range(120))
    asset_id = upload("demo", "long_notes.txt", body.encode()).asset["id"]

    run_once()

    settings = get_settings()
    chunks = chunk_text(body, settings.chunk_size_chars, settings.chunk_overlap_chars)
    assert len(chunks) >= 3
    units = load_units(db, asset_id)
    content_units = [unit for unit in units if unit["kind"] == "content"]
    assert len(units) == len(chunks) + 2
    assert [(unit["start_char"], unit["end_char"]) for unit in content_units] == [
        (chunk.start, chunk.end) for chunk in chunks
    ]
    assert load_asset(db, asset_id)["tags"][-3:] == ["text", "text file", "document"]


def test_text_file_has_null_visible_text(db, blob_store):
    asset_id = upload("demo", "short_note.txt", b"A short note about the harbour.").asset["id"]

    run_once()

    asset = load_asset(db, asset_id)
    assert asset["status"] == "ready"
    assert asset["visible_text"] is None


def test_run_once_returns_false_on_empty_queue(db, blob_store):
    assert run_once() is False


def test_claim_skips_a_locked_row(db, blob_store):
    first_id = upload("demo", "first.txt", b"first note").asset["id"]
    second_id = upload("demo", "second.txt", b"second note").asset["id"]

    with db.connect() as other_worker:
        transaction = other_worker.begin()
        other_worker.execute(
            text("SELECT id FROM assets WHERE id = :id FOR UPDATE"), {"id": first_id}
        )
        claimed = claim_one()
        transaction.rollback()

    assert claimed["id"] == second_id


def test_failed_attempt_returns_to_pending_with_error(db, blob_store):
    asset_id = upload("demo", "notes_invalid.txt", NOTE).asset["id"]

    run_once()

    asset = load_asset(db, asset_id)
    assert asset["status"] == "pending"
    assert asset["attempts"] == 1
    assert asset["error"].startswith("ValidationError:")
    assert load_units(db, asset_id) == []


def test_third_failure_marks_failed(db, blob_store):
    asset_id = upload("demo", "notes_invalid.txt", NOTE).asset["id"]

    for _ in range(get_settings().max_attempts):
        run_once()

    asset = load_asset(db, asset_id)
    assert asset["status"] == "failed"
    assert asset["attempts"] == get_settings().max_attempts
    assert asset["error"].startswith("ValidationError:")
    assert run_once() is False


def test_retry_resets_a_failed_asset(client, db):
    response = client.post(
        "/api/assets",
        data={"collection": "demo"},
        files={"file": ("notes_invalid.txt", NOTE, "text/plain")},
    )
    asset_id = response.json()["asset"]["id"]
    for _ in range(get_settings().max_attempts):
        run_once()
    assert load_asset(db, asset_id)["status"] == "failed"

    assert client.post(f"/api/assets/{asset_id}/retry").json()["status"] == "pending"
    retried = load_asset(db, asset_id)
    assert (retried["attempts"], retried["error"]) == (0, None)

    assert run_once() is True
    assert load_asset(db, asset_id)["attempts"] == 1


def test_reaper_resets_stale_and_leaves_fresh(db, blob_store):
    stale_id = upload("demo", "stale.txt", b"stale note").asset["id"]
    fresh_id = upload("demo", "fresh.txt", b"fresh note").asset["id"]
    claim_one()
    claim_one()
    expire_lease(db, stale_id)

    assert reaper() == 1

    stale = load_asset(db, stale_id)
    assert (stale["status"], stale["started_at"]) == ("pending", None)
    assert load_asset(db, fresh_id)["status"] == "processing"


def test_reaper_fails_an_expired_asset_at_the_cap(db, blob_store):
    asset_id = upload("demo", "crashes.txt", b"kills its worker").asset["id"]
    with db.begin() as connection:
        connection.execute(
            text("UPDATE assets SET attempts = :attempts WHERE id = :id"),
            {"attempts": get_settings().max_attempts - 1, "id": asset_id},
        )
    claim_one()
    expire_lease(db, asset_id)

    reaper()

    asset = load_asset(db, asset_id)
    assert asset["status"] == "failed"
    assert "did not finish within the lease" in asset["error"]


def test_stale_worker_cannot_commit(db, blob_store):
    asset_id = upload("demo", "slow.txt", NOTE).asset["id"]
    stale_claim = claim_one()
    expire_lease(db, asset_id)
    reaper()
    fresh_claim = claim_one()
    assert fresh_claim["id"] == asset_id

    metadata = normalise(
        Metadata(title="t", description="d", tags=[], visible_text="", image_type=None), "text"
    )
    units = build_units("text", "slow.txt", metadata, None, [])
    vectors = get_embedder().embed([unit.embed_input for unit in units], "document")

    assert commit_ready(stale_claim, metadata, "fake-vision", units, vectors) is False
    assert load_asset(db, asset_id)["status"] == "processing"
    assert load_units(db, asset_id) == []
