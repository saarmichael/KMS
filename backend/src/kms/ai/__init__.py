"""The process-wide vision and embedding adapters, chosen by AI_PROVIDER on first use
(same pattern as blob.get_blob_store)."""

from kms.ai.fake import FakeEmbedder, FakeVision
from kms.ai.interfaces import Embedder, Vision
from kms.config import get_settings

REAL_NOT_AVAILABLE = "AI_PROVIDER=real is not available yet"

_vision: Vision | None = None
_embedder: Embedder | None = None


def get_vision() -> Vision:
    global _vision
    if _vision is None:
        if get_settings().ai_provider == "real":
            raise NotImplementedError(REAL_NOT_AVAILABLE)
        _vision = FakeVision()
    return _vision


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        settings = get_settings()
        if settings.ai_provider == "real":
            raise NotImplementedError(REAL_NOT_AVAILABLE)
        _embedder = FakeEmbedder(settings.embedding_dims)
    return _embedder


def set_vision(vision: Vision | None) -> None:
    """Tests inject an adapter, or reset to None so the next call builds one from settings."""
    global _vision
    _vision = vision


def set_embedder(embedder: Embedder | None) -> None:
    """Tests inject an adapter, or reset to None so the next call builds one from settings."""
    global _embedder
    _embedder = embedder
