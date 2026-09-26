import threading

import pytest
from sqlalchemy import text

from kms.db import ASSET_PENDING_CHANNEL, listen_connection
from kms.ingest.upload import FileTooLarge, upload

NOTE = b"A short note about a woman with black hair.\n"


def received_asset_ids(listener, timeout: float) -> list[str]:
    """Payloads of every notification that arrives within the timeout."""
    return [notification.payload for notification in listener.notifies(timeout=timeout)]


def asset_rows(db):
    with db.connect() as connection:
        return connection.execute(text("SELECT * FROM assets")).mappings().all()


def test_upload_creates_pending_row_blob_and_notify(db, blob_store):
    with listen_connection(ASSET_PENDING_CHANNEL) as listener:
        result = upload("demo", "note.txt", NOTE)
        notified = received_asset_ids(listener, timeout=1)

    assert result.deduplicated is False
    asset = result.asset
    assert asset["status"] == "pending"
    assert asset["attempts"] == 0
    assert (asset["asset_type"], asset["mime"]) == ("text", "text/plain")
    assert asset["size_bytes"] == len(NOTE)
    assert blob_store.get(asset["sha256"]) == NOTE
    assert notified == [str(asset["id"])]


def test_same_bytes_twice_is_one_row_with_alias(db, blob_store):
    first = upload("demo", "a.txt", NOTE)
    with listen_connection(ASSET_PENDING_CHANNEL) as listener:
        second = upload("demo", "b.txt", NOTE)
        notified = received_asset_ids(listener, timeout=0.5)

    assert second.deduplicated is True
    assert second.asset["id"] == first.asset["id"]
    assert second.asset["filename"] == "a.txt"
    assert second.asset["aliases"] == ["b.txt"]
    assert len(asset_rows(db)) == 1
    assert notified == []


def test_same_name_twice_adds_no_alias(db, blob_store):
    upload("demo", "a.txt", NOTE)
    upload("demo", "b.txt", NOTE)
    again_original = upload("demo", "a.txt", NOTE)
    again_alias = upload("demo", "b.txt", NOTE)

    assert again_original.asset["aliases"] == ["b.txt"]
    assert again_alias.asset["aliases"] == ["b.txt"]


def test_same_bytes_in_another_collection_is_a_new_asset(db, blob_store):
    in_demo = upload("demo", "a.txt", NOTE)
    in_other = upload("other", "a.txt", NOTE)

    assert in_other.deduplicated is False
    assert in_other.asset["id"] != in_demo.asset["id"]
    assert len(asset_rows(db)) == 2
    assert len(list(blob_store.root.iterdir())) == 1


def test_concurrent_identical_uploads_make_one_row(db, blob_store):
    thread_count = 8
    # The barrier holds every thread until all have arrived, so the inserts really collide.
    barrier = threading.Barrier(thread_count)
    results = []

    def upload_after_barrier(index: int) -> None:
        barrier.wait()
        results.append(upload("demo", f"copy-{index}.txt", NOTE))

    threads = [
        threading.Thread(target=upload_after_barrier, args=(index,))
        for index in range(thread_count)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    rows = asset_rows(db)
    assert len(rows) == 1
    assert [result.deduplicated for result in results].count(False) == 1
    assert [result.deduplicated for result in results].count(True) == thread_count - 1
    # Every other name became an alias: none was lost to a concurrent update.
    assert len(rows[0]["aliases"]) == thread_count - 1


def test_upload_over_the_limit_raises_file_too_large(db, blob_store):
    too_big = b"a" * (10 * 1024 * 1024 + 1)
    with pytest.raises(FileTooLarge, match="10 MB"):
        upload("demo", "big.txt", too_big)
    assert asset_rows(db) == []


def test_duplicate_of_failed_asset_comes_back_failed(db, blob_store):
    first = upload("demo", "a.txt", NOTE)
    with db.begin() as connection:
        connection.execute(
            text("UPDATE assets SET status = 'failed', error = 'boom' WHERE id = :id"),
            {"id": first.asset["id"]},
        )

    duplicate = upload("demo", "b.txt", NOTE)

    assert duplicate.deduplicated is True
    assert duplicate.asset["status"] == "failed"
    assert duplicate.asset["error"] == "boom"
