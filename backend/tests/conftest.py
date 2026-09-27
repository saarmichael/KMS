"""Shared fixtures. Integration tests hit the compose Postgres, database `kms_test`,
migrated to head once per session and truncated between tests."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from kms import db as kms_db
from kms.blob import set_blob_store
from kms.blob.store import LocalBlobStore
from kms.config import get_settings
from kms.migrations import upgrade_head

# Tests drive the worker themselves, so the app must not start its own pool. Set before any
# test reads the settings, which are cached on first read; the environment wins over .env.
os.environ["WORKER_ENABLED"] = "false"
# Tests assert on the fake adapters' fixtures, and must never call a vendor because .env says
# "real". The live tests switch to the real provider themselves.
os.environ["AI_PROVIDER"] = "fake"


@pytest.fixture(scope="session")
def test_engine():
    url = get_settings().test_database_url
    upgrade_head(url)
    engine = create_engine(url, pool_pre_ping=True)
    kms_db.set_engine(engine)
    yield engine
    engine.dispose()
    kms_db.set_engine(None)


@pytest.fixture
def db(test_engine):
    """A migrated, empty database for one test."""
    with test_engine.begin() as conn:
        conn.execute(text("TRUNCATE search_units, assets"))
    yield test_engine


@pytest.fixture
def blob_store(tmp_path):
    """A blob store on a fresh temporary folder, so tests never write into BLOB_DIR."""
    store = LocalBlobStore(tmp_path / "blobs")
    set_blob_store(store)
    yield store
    set_blob_store(None)


@pytest.fixture
def client(db, blob_store):
    from kms.main import create_app

    with TestClient(create_app()) as c:
        yield c
