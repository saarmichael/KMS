"""Shared fixtures. Integration tests hit the compose Postgres, database `kms_test`,
migrated to head once per session and truncated between tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from kms import db as kms_db
from kms.config import get_settings
from kms.migrations import upgrade_head


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
def client(db):
    from kms.main import create_app

    with TestClient(create_app()) as c:
        yield c
