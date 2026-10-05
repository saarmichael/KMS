import typing

import pytest
from pydantic import ValidationError

from kms.blob import BLOB_STORE_BUILDERS, get_blob_store, set_blob_store
from kms.blob.store import LocalBlobStore
from kms.config import Settings, get_settings

HASH = "a" * 64


def test_put_then_get_returns_the_bytes(tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    store.put(HASH, b"hello")
    assert store.get(HASH) == b"hello"


def test_put_same_hash_twice_is_harmless(tmp_path):
    store = LocalBlobStore(tmp_path)
    store.put(HASH, b"hello")
    store.put(HASH, b"hello")
    assert store.get(HASH) == b"hello"
    assert [file.name for file in tmp_path.iterdir()] == [HASH]


def test_get_unknown_hash_raises_file_not_found(tmp_path):
    store = LocalBlobStore(tmp_path)
    with pytest.raises(FileNotFoundError):
        store.get(HASH)


def test_every_blob_store_name_has_a_builder():
    store_names = typing.get_args(Settings.model_fields["blob_store"].annotation)
    assert set(store_names) == set(BLOB_STORE_BUILDERS)


def test_unknown_blob_store_is_refused(monkeypatch):
    monkeypatch.setenv("BLOB_STORE", "s3")
    with pytest.raises(ValidationError, match="blob_store"):
        Settings(_env_file=None)


def test_local_blob_store_is_built_from_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("BLOB_STORE", "local")
    monkeypatch.setenv("BLOB_DIR", str(tmp_path))
    # The settings and the store are cached per process, so both are reset on the way in and
    # out; otherwise this test's folder would leak into the next test.
    get_settings.cache_clear()
    set_blob_store(None)
    try:
        store = get_blob_store()
        assert isinstance(store, LocalBlobStore)
        assert store.root == tmp_path
    finally:
        get_settings.cache_clear()
        set_blob_store(None)
