import pytest

from kms.blob.store import LocalBlobStore

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
