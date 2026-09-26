"""The process-wide blob store, built from settings on first use (same pattern as db.get_engine)."""

from kms.blob.store import BlobStore, LocalBlobStore
from kms.config import get_settings

_store: BlobStore | None = None


def get_blob_store() -> BlobStore:
    global _store
    if _store is None:
        _store = LocalBlobStore(get_settings().blob_dir)
    return _store


def set_blob_store(store: BlobStore | None) -> None:
    """Tests inject a store on a temporary folder."""
    global _store
    _store = store
