import hashlib
import uuid

from sqlalchemy import text

from kms.db import ASSET_PENDING_CHANNEL, listen_connection
from kms.ingest.worker import run_once

NOTE = b"A short note about a woman with black hair.\n"
OTHER_NOTE = b"The quarterly report is on the desk.\n"

ASSET_KEYS = {
    "id",
    "collection",
    "filename",
    "aliases",
    "asset_type",
    "mime",
    "size_bytes",
    "status",
    "error",
    "created_at",
    "metadata",
}


def post_file(client, filename: str, data: bytes, collection: str = "demo"):
    return client.post(
        "/api/assets",
        files={"file": (filename, data, "application/octet-stream")},
        data={"collection": collection},
    )


def test_upload_answers_202_then_200_deduplicated(client):
    first = post_file(client, "a.txt", NOTE)
    assert first.status_code == 202
    body = first.json()
    assert body["deduplicated"] is False
    assert set(body["asset"]) == ASSET_KEYS
    assert body["asset"]["status"] == "pending"
    assert body["asset"]["metadata"] is None
    assert body["asset"]["aliases"] == []
    assert body["asset"]["created_at"].endswith("Z")

    second = post_file(client, "b.txt", NOTE)
    assert second.status_code == 200
    assert second.json()["deduplicated"] is True
    assert second.json()["asset"]["id"] == body["asset"]["id"]
    assert second.json()["asset"]["aliases"] == ["b.txt"]


def test_upload_over_limit_is_413(client):
    response = post_file(client, "big.txt", b"a" * (10 * 1024 * 1024 + 1))
    assert response.status_code == 413
    assert response.json() == {"detail": "File is larger than the 10 MB limit."}


def test_upload_unsupported_type_is_415(client):
    response = post_file(client, "blob.bin", bytes(range(256)))
    assert response.status_code == 415
    assert "Unsupported file type" in response.json()["detail"]


def test_bad_collection_name_is_422_with_a_string_detail(client):
    bad_upload = post_file(client, "a.txt", NOTE, collection="Bad Name")
    assert bad_upload.status_code == 422
    assert isinstance(bad_upload.json()["detail"], str)
    assert bad_upload.json()["detail"].startswith("collection:")

    missing_collection = client.get("/api/assets")
    assert missing_collection.status_code == 422
    assert isinstance(missing_collection.json()["detail"], str)


def test_list_is_newest_first_and_scoped_to_the_collection(client):
    older = post_file(client, "older.txt", NOTE).json()["asset"]
    newer = post_file(client, "newer.txt", OTHER_NOTE).json()["asset"]
    post_file(client, "elsewhere.txt", NOTE, collection="other")

    response = client.get("/api/assets", params={"collection": "demo"})
    assert response.status_code == 200
    listed_ids = [asset["id"] for asset in response.json()["assets"]]
    assert listed_ids == [newer["id"], older["id"]]

    unknown = client.get("/api/assets", params={"collection": "nobody"})
    assert unknown.json() == {"assets": []}


def test_unknown_asset_is_404(client):
    unknown_id = uuid.uuid4()
    for path in (f"/api/assets/{unknown_id}", f"/api/assets/{unknown_id}/file"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json() == {"detail": "Asset not found."}
    assert client.post(f"/api/assets/{unknown_id}/retry").status_code == 404
    assert client.get("/api/assets/not-a-uuid").status_code == 422


def test_ready_asset_reports_the_model_that_described_it(client):
    asset = post_file(client, "a.txt", NOTE).json()["asset"]

    assert run_once() is True

    response = client.get(f"/api/assets/{asset['id']}")
    assert response.status_code == 200
    assert response.json()["metadata"]["vision_model"] == "fake-vision"


def test_file_has_etag_and_immutable_cache_headers(client):
    asset = post_file(client, "a.txt", NOTE).json()["asset"]

    response = client.get(f"/api/assets/{asset['id']}/file")
    assert response.status_code == 200
    assert response.content == NOTE
    assert response.headers["etag"] == f'"{hashlib.sha256(NOTE).hexdigest()}"'
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.headers["content-disposition"] == 'inline; filename="a.txt"'

    non_ascii = post_file(client, "café.txt", OTHER_NOTE).json()["asset"]
    response = client.get(f"/api/assets/{non_ascii['id']}/file")
    assert response.headers["content-disposition"] == "inline; filename*=utf-8''caf%C3%A9.txt"

    with_space = post_file(client, "my notes.txt", NOTE + b"!").json()["asset"]
    response = client.get(f"/api/assets/{with_space['id']}/file")
    assert response.headers["content-disposition"] == "inline; filename*=utf-8''my%20notes.txt"


def test_retry_resets_a_failed_asset_and_refuses_others(client, db):
    asset = post_file(client, "a.txt", NOTE).json()["asset"]

    pending_retry = client.post(f"/api/assets/{asset['id']}/retry")
    assert pending_retry.status_code == 409
    assert "pending" in pending_retry.json()["detail"]

    with db.begin() as connection:
        connection.execute(
            text(
                "UPDATE assets SET status = 'failed', error = 'boom', attempts = 3, "
                "started_at = now() WHERE id = :id"
            ),
            {"id": asset["id"]},
        )

    with listen_connection(ASSET_PENDING_CHANNEL) as listener:
        retried = client.post(f"/api/assets/{asset['id']}/retry")
        notified = [notification.payload for notification in listener.notifies(timeout=1)]

    assert retried.status_code == 200
    assert retried.json()["status"] == "pending"
    assert retried.json()["error"] is None
    assert notified == [asset["id"]]
    with db.connect() as connection:
        attempts, started_at = connection.execute(
            text("SELECT attempts, started_at FROM assets WHERE id = :id"), {"id": asset["id"]}
        ).one()
    assert (attempts, started_at) == (0, None)


def test_collections_have_counts_and_delete_is_idempotent(client):
    post_file(client, "a.txt", NOTE)
    post_file(client, "b.txt", OTHER_NOTE)
    post_file(client, "c.txt", NOTE, collection="another")

    listed = client.get("/api/collections")
    assert listed.json() == {
        "collections": [
            {"name": "another", "asset_count": 1},
            {"name": "demo", "asset_count": 2},
        ]
    }

    assert client.delete("/api/collections/demo").status_code == 204
    assert client.get("/api/collections").json() == {
        "collections": [{"name": "another", "asset_count": 1}]
    }
    assert client.delete("/api/collections/demo").status_code == 204
    assert client.delete("/api/collections/Bad Name").status_code == 422
