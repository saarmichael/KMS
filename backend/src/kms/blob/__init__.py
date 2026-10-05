"""The process-wide blob store, built on first use by the store BLOB_STORE names (same pattern as
db.get_engine)."""

import logging
from collections.abc import Callable

from kms.blob.store import BlobStore, build_local_blob_store
from kms.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Store name to builder, so that adding a store is one line here and the getter below never changes.
BLOB_STORE_BUILDERS: dict[str, Callable[[Settings], BlobStore]] = {
    "local": build_local_blob_store,
}

_store: BlobStore | None = None


def get_blob_store() -> BlobStore:
    """Return the process-wide blob store, building it from settings on first use.

    Returns:
        The store built by BLOB_STORE's builder.
    """
    global _store
    if _store is None:
        settings = get_settings()
        _store = BLOB_STORE_BUILDERS[settings.blob_store](settings)
        logger.info("blob_store_selected store=%s", settings.blob_store)
    return _store


def set_blob_store(store: BlobStore | None) -> None:
    """Replace the process-wide blob store; tests inject one on a temporary folder.

    Args:
        store: The store to use from now on, or None to build one from settings on next use.
    """
    global _store
    _store = store
