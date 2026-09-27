"""The process-wide vision and embedding adapters, chosen by AI_PROVIDER on first use
(same pattern as blob.get_blob_store)."""

from kms.ai.fake import FakeEmbedder, FakeVision
from kms.ai.interfaces import Embedder, Vision
from kms.config import get_settings

REAL_NOT_AVAILABLE = "AI_PROVIDER=real is not available yet"

_vision: Vision | None = None
_embedder: Embedder | None = None


def get_vision() -> Vision:
    """Return the shared vision adapter, building it from settings on first use.

    Returns:
        FakeVision when AI_PROVIDER is "fake".

    Raises:
        NotImplementedError: AI_PROVIDER is "real".
    """
    global _vision
    if _vision is None:
        if get_settings().ai_provider == "real":
            raise NotImplementedError(REAL_NOT_AVAILABLE)
        _vision = FakeVision()
    return _vision


def get_embedder() -> Embedder:
    """Return the shared embedder, building it from settings on first use.

    Returns:
        FakeEmbedder with EMBEDDING_DIMS dimensions when AI_PROVIDER is "fake".

    Raises:
        NotImplementedError: AI_PROVIDER is "real".
    """
    global _embedder
    if _embedder is None:
        settings = get_settings()
        if settings.ai_provider == "real":
            raise NotImplementedError(REAL_NOT_AVAILABLE)
        _embedder = FakeEmbedder(settings.embedding_dims)
    return _embedder


def set_vision(vision: Vision | None) -> None:
    """Replace the shared vision adapter; tests use it.

    Args:
        vision: The adapter to use, or None so the next call builds one from settings.
    """
    global _vision
    _vision = vision


def set_embedder(embedder: Embedder | None) -> None:
    """Replace the shared embedder; tests use it.

    Args:
        embedder: The embedder to use, or None so the next call builds one from settings.
    """
    global _embedder
    _embedder = embedder
