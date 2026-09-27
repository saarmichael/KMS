"""The process-wide blob store, built from settings on first use (same pattern as db.get_engine)."""

from kms.blob.store import BlobStore, LocalBlobStore
from kms.config import get_settings

_store: BlobStore | None = None


def get_blob_store() -> BlobStore:
    """The process-wide blob store, created from settings on first use."""
    global _store
    if _store is None:
        _store = LocalBlobStore(get_settings().blob_dir)
    return _store


def set_blob_store(store: BlobStore | None) -> None:
    """Replace the process-wide blob store; tests inject one on a temporary folder.

    Args:
        store: The store to use from now on, or None to build one from settings on next use.
    """
    global _store
    _store = store
