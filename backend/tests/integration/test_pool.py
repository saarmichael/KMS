import time

from sqlalchemy import text

from kms.ingest.pool import WorkerPool
from kms.ingest.upload import upload

NOTE = b"A short note about a woman with black hair.\n"


def asset_status(db, asset_id) -> str:
    with db.connect() as connection:
        return connection.execute(
            text("SELECT status FROM assets WHERE id = :id"), {"id": asset_id}
        ).scalar_one()


def test_pool_processes_an_upload(db, blob_store):
    pool = WorkerPool(1)
    pool.start()
    try:
        asset_id = upload("demo", "note.txt", NOTE).asset["id"]
        deadline = time.monotonic() + 5
        while asset_status(db, asset_id) != "ready" and time.monotonic() < deadline:
            time.sleep(0.1)
        assert asset_status(db, asset_id) == "ready"
    finally:
        pool.stop()


def test_stop_ends_every_thread(db, blob_store):
    pool = WorkerPool(2)
    pool.start()

    pool.stop()

    assert [thread.name for thread in pool._threads if thread.is_alive()] == []
